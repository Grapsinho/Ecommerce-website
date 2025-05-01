from django.db.models import Q, Prefetch
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import CursorPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from product_management.models import Product, Category, ProductMedia
from product_cart.models import CartItem
from orders.models import OrderItem
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
    # cache per-user & per-limit
    cache_key_func = lambda view, method, req, args, kwargs: (
        f"recs_user_{req.user.id}_lim_{req.query_params.get('limit', 10)}"
    )
    cache_response_timeout = 60 * 5

    serializer_class       = RecommendationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes     = [IsAuthenticated]
    pagination_class       = None   # disable DRF pagination

    # single Prefetch for “feature_media”
    feature_media_prefetch = Prefetch(
        'media',
        queryset=ProductMedia.objects.filter(is_feature=True),
        to_attr='feature_media'
    )

    def list(self, request, *args, **kwargs):
        user  = request.user
        limit = self._get_limit(request)

        recs = self._build_recommendations(user, limit)
        serializer = self.get_serializer(recs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_limit(self, request):
        try:
            raw = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            raw = 10
        return max(1, min(raw, 10))

    def _build_recommendations(self, user, limit):
        # 1) collect IDs to exclude
        purchased_ids = set(
            OrderItem.objects.filter(order__user=user)
                             .values_list('product_id', flat=True)
        )
        cart_ids = set(
            CartItem.objects.filter(cart__user=user)
                            .values_list('product_id', flat=True)
        )
        exclude_ids = purchased_ids | cart_ids

        # 2) base QuerySet for all sections
        base_qs = (
            Product.objects
                   .filter(is_active=True, stock__gt=0)
                   .exclude(Q(id__in=exclude_ids) | Q(seller=user))
                   .prefetch_related(self.feature_media_prefetch)
        )

        recs = []

        # — A) Wishlist & Cart categories —
        user_cat_ids = self._get_user_category_ids(user)
        if user_cat_ids:
            qs_a = base_qs.filter(category_id__in=user_cat_ids) \
                         .order_by('-units_sold')[:limit]
            recs.extend(qs_a)

        # — B) Sibling‐category cross‐sells —
        if len(recs) < limit:
            needed = limit - len(recs)
            sibling_cat_ids = self._get_sibling_category_ids(user)
            qs_b = base_qs.filter(category_id__in=sibling_cat_ids) \
                         .order_by('-units_sold')[:needed]
            recs.extend(qs_b)

        # — C) Fallback bestsellers —
        if len(recs) < limit:
            needed = limit - len(recs)
            used_ids = {p.id for p in recs}
            qs_c = base_qs.exclude(id__in=used_ids) \
                         .order_by('-units_sold')[:needed]
            recs.extend(qs_c)

        return recs

    def _get_user_category_ids(self, user):
        # distinct category IDs from wishlist OR cart
        return (
            Product.objects
                   .filter(
                       Q(wishlist_items__wishlist__user=user) |
                       Q(cartitem__cart__user=user)
                   )
                   .values_list('category_id', flat=True)
                   .distinct()
        )

    def _get_sibling_category_ids(self, user):
        # categories of purchased products
        bought_cat_ids = (
            OrderItem.objects
                     .filter(order__user=user)
                     .values_list('product__category_id', flat=True)
                     .distinct()
        )
        parent_ids = (
            Category.objects
                    .filter(pk__in=bought_cat_ids)
                    .values_list('parent_id', flat=True)
                    .distinct()
        )
        return (
            Category.objects
                    .filter(parent_id__in=parent_ids)
                    .exclude(pk__in=bought_cat_ids)
                    .values_list('pk', flat=True)
        )
