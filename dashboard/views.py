from django.db.models import Q, Prefetch
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import CursorPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from product_management.models import Product, ProductMedia
from .services import Recommendations
from .filters import MyProductFilter
from users.authentication import JWTAuthentication
from .serializers import (
    ProfileSerializer,
    MyProductSerializer,
    RecommendationSerializer
)

# 1. Profile Update
class ProfileUpdateView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /dashboard/profile/current/
    """
    serializer_class = ProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

# 2. Pagination & Filters for Products
class StandardCursorPagination(CursorPagination):
    page_size = 10
    ordering = '-created_at'

# 3. My Products List
class MyProductListView(generics.ListAPIView):
    """
    GET /dashboard/me/products/
    """
    serializer_class = MyProductSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = StandardCursorPagination
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = ['price', 'stock', 'units_sold']
    filterset_class = MyProductFilter

    def get_queryset(self):
        return (
            Product.objects.filter(seller=self.request.user)
            .prefetch_related(
                Prefetch(
                    'media',
                    queryset=ProductMedia.objects.filter(is_feature=True),
                    to_attr='feature_media'
                )
            )
        )

# 4. Recommendations
class RecommendationView(CacheResponseMixin, generics.ListAPIView):
    """
    GET /dashboard/me/recommendations/?limit=10
    """
    cache_key_func = lambda view, method, req, args, kwargs: (
        f"recs_user_{req.user.id}_lim_{req.query_params.get('limit', 10)}"
    )
    cache_response_timeout = 60 * 5

    serializer_class = RecommendationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        user = request.user
        limit = request.query_params.get('limit', 10)
        recs = Recommendations.for_user(user, limit)

        serializer = self.get_serializer(recs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)