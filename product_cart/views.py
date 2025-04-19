from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import CartItem
from rest_framework.response import Response

from .serializers import CartItemSerializer
from product_management.models import ProductMedia
from django.db.models import Prefetch
from django.db import transaction
from users.authentication import JWTAuthentication

from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter
)


@extend_schema_view(
    list=extend_schema(
        summary="List all items in the authenticated user's cart",
        responses=CartItemSerializer
    ),
    create=extend_schema(
        summary="Add a new item to the cart",
        request=CartItemSerializer,
        responses=CartItemSerializer
    ),
    retrieve=extend_schema(
        summary="Retrieve a single cart item",
        parameters=[
            OpenApiParameter(
                name='pk',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID of the CartItem to retrieve'
            )
        ],
        responses=CartItemSerializer
    ),
    update=extend_schema(
        summary="Update an existing cart item's quantity",
        request=CartItemSerializer,
        responses=CartItemSerializer
    ),
    partial_update=extend_schema(
        summary="Partially update a cart item's quantity",
        request=CartItemSerializer,
        responses=CartItemSerializer
    ),
    destroy=extend_schema(
        summary="Remove an item from the cart",
        responses=None
    )
)
class CartItemViewSet(viewsets.ModelViewSet):
    """
    CRUD for cart items + cart summary in list.
    """
    serializer_class       = CartItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes     = [IsAuthenticated]
    lookup_value_regex     = r'\d+'

    def get_queryset(self):
        cart = self.request.user.cart
        return (
            CartItem.objects
                    .filter(cart=cart)
                    .select_related('product')
                    .prefetch_related(
                        Prefetch(
                            'product__media',
                            queryset=ProductMedia.objects.filter(is_feature=True),
                            to_attr='featured_media'
                        )
                    )
        )

    def list(self, request, *args, **kwargs):
        # Return cart items plus cached total_price
        qs = self.get_queryset()
        items_data = self.get_serializer(qs, many=True).data
        total = request.user.cart.total_price
        return Response({
            'total_price': total,
            'items': items_data
        })

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()
