from django.db import transaction
from django.db.models import Prefetch, Max, Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import APIException
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import extend_schema, extend_schema_view

import logging

from .models import Product, ProductMedia, Category
from .serializers import (
    ProductWriteSerializer,
    ProductRetrieveSerializer,
    CategorySerializer,
    ProductListSerializer,
    SimpleCategorySerializer, 
    ProductUpdateRetrieveSerializer
)
from .filters import ProductFilter
from .pagination import ProductPagination
from users.authentication import JWTAuthentication
from .permissions import IsOwnerOrAdmin
from utils.product_search import apply_full_text_search, apply_active_filter

logger = logging.getLogger("rest_framework")



# -------------------------------------------------
# API Documentation using drf-spectacular
# -------------------------------------------------
@extend_schema_view(
    list=extend_schema(
        summary="List Products",
        description=(
            "Retrieve a paginated list of all active products. Supports filtering by price, "
            "condition, category, and ordering by specified fields. Uses optimized queries with related "
            "seller, media, and category data. Additionally, supports full-text search with relevance ranking "
            "by providing a `q` parameter, and optionally searching by owner when an `owner` parameter is provided."
        )
    ),
    retrieve=extend_schema(
        summary="Retrieve Product",
        description=(
            "Retrieve detailed information for a single product by its slug. Returned data includes nested images, "
            "a category breadcrumb, and seller details."
        )
    ),
    create=extend_schema(
        summary="Create Product",
        description=(
            "Create a new product. The authenticated user is automatically set as the seller. Required fields "
            "include name, description, price, stock, condition, category, and optionally images (with one featured)."
        )
    ),
    update=extend_schema(
        summary="Update Product",
        description=(
            "Update an existing product. Only the product owner or an admin may update the product. The operation "
            "is performed even if the product is in an active cart."
        )
    ),
    partial_update=extend_schema(
        summary="Partial Update Product",
        description="Partially update a product (allowed for the owner or admin)."
    ),
    destroy=extend_schema(
        summary="Delete Product",
        description=(
            "Delete a product along with its associated media files in an atomic transaction. "
            "This operation does not check for active cart associations."
        )
    ),
)
class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing products.

    GET requests are public (only active products are returned) and
    enriched with related seller, media, and breadcrumb category data.
    POST/PUT/PATCH/DELETE require JWT authentication; only the product owner or an admin can modify.

    Additional enhancements:
      - **Caching:** The list view is cached for 5 minutes.
      - **Ordering:** Supports ordering by fields such as 'price', 'created_at', 'units_sold'.
      - **Throttling:** Rate limiting is applied for both anonymous and authenticated users.
      - **Search:** Full-text search using PostgreSQL, with optional owner-based filtering.
    """

    queryset = Product.objects.all()
    authentication_classes = [JWTAuthentication]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductFilter
    pagination_class = ProductPagination

    # Expose ordering fields for GET queries
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']  # Default ordering

    # Apply throttling to all endpoints in this viewset
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def get_serializer_class(self):
        # For GET requests, choose serializer based on action
        if self.request and self.request.method == 'GET':
            if self.action == 'retrieve':
                # If the query parameter 'edit' is present, return the update serializer.
                if self.request.query_params.get('edit') == 'true':
                    return ProductUpdateRetrieveSerializer
                return ProductRetrieveSerializer
            elif self.action == 'list':
                return ProductListSerializer
        # For non-GET requests use the write serializer.
        return ProductWriteSerializer

    def get_authenticators(self):
        if self.request and self.request.method == 'GET':
            return []  # Public access for GET requests.
        return [JWTAuthentication()]

    def get_permissions(self):
        if self.request and self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        return [AllowAny()]

    def get_queryset(self):

        if self.request and self.request.method == 'GET' and self.action == 'list':
            queryset = Product.objects.prefetch_related(
                Prefetch('media', queryset=ProductMedia.objects.filter(is_feature=True).only(
                    'id', 'image', 'is_feature', 'created_at', 'product'
                ))
            ).only(
                'id', 'name', 'description', 'slug', 'price', 'stock',
                'condition', 'created_at', 'updated_at', 'is_active'
            )
        else:
            queryset = Product.objects.select_related(
                'seller', 'category', 'category__parent'
            ).prefetch_related(
                Prefetch('media', queryset=ProductMedia.objects.only(
                    'id', 'image', 'is_feature', 'created_at', 'product'
                ))
            ).only(
                'id', 'name', 'description', 'slug', 'price', 'stock',
                'condition', 'created_at', 'updated_at', 'seller', 'is_active', 'category'
            )

        # Apply active filter.
        queryset = apply_active_filter(queryset, self.request)

        # Apply full-text search (if applicable).
        queryset = apply_full_text_search(queryset, self.request)

        return queryset

    @method_decorator(cache_page(60 * 3, key_prefix="product_management:product_list"), name="list")
    def list(self, request, *args, **kwargs):
        filtered_queryset = self.filter_queryset(self.get_queryset())
        aggregated = filtered_queryset.aggregate(max_price=Max('price'))
        max_price = aggregated.get('max_price') or 0.1

        response = super().list(request, *args, **kwargs)
        response.data['price_range'] = {"min_price": 0.1, "max_price": max_price}

        return response

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                for media in instance.media.all():
                    try:
                        media.image.delete(save=False)
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete image file for ProductMedia ID {media.id}: {str(e)}"
                        )
                    media.delete()
                instance.delete()

        except Exception as e:
            logger.exception(f"Error occurred during product deletion: {str(e)}")
            raise APIException("An error occurred while deleting the product. Please try again later.")
        

class CategoryRetrieveAPIView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve a category and its children recursively.
    The lookup is done by the category slug.
    """
    serializer_class = CategorySerializer
    lookup_field = 'slug'

    def get_queryset(self):
        # Load the category along with multiple levels of children.
        return Category.objects.all().prefetch_related(
            'children', 'children__children', 'children__children__children'
        )

class ParentCategoryListAPIView(generics.ListAPIView):
    """
    API endpoint to retrieve parent categories without nested children.
    This is optimized for cases where child data is not needed.
    """
    serializer_class = SimpleCategorySerializer

    def get_queryset(self):
        # Return only parent categories.
        return Category.objects.filter(parent__isnull=True)