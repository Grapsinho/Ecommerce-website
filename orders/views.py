from rest_framework import permissions, viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Prefetch

from users.authentication import JWTAuthentication
from .models import Order, OrderItem
from .serializers import (
    OrderSerializer, OrderDetailSerializer,
    CheckoutSerializer, AddressSerializer
)
from .pagination import OrderCursorPagination
from .services import OrderService
from product_management.models import ProductMedia

import logging
logger = logging.getLogger("rest_framework")

class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderCursorPagination

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user, items__isnull=False)
                 .select_related('shipping_method', 'shipping_address')
                 .prefetch_related(
                     Prefetch(
                         'items',
                         queryset=OrderItem.objects
                             .select_related('product', 'product__seller')
                             .prefetch_related(
                                 Prefetch(
                                     'product__media',
                                     queryset=ProductMedia.objects.filter(is_feature=True),
                                     to_attr='feature_media'
                                 )
                             )
                     )
                 )
                 .distinct()
                 .order_by('-created_at')
        )

    def get_serializer_class(self):

        if self.request and self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderSerializer

    @action(detail=False, methods=['get'], url_path='default-address')
    def default_address(self, request):
        user = request.user
        if hasattr(user, 'address'):
            return Response(AddressSerializer(user.address).data)
        return Response(None, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        user = request.user
        idem_key = request.headers.get('Idempotency-Key')
        cache_key = f"checkout:{user.id}:{idem_key}" if idem_key else None
        if cache_key and (cached := cache.get(cache_key)) is not None:
            return Response(cached, status=status.HTTP_200_OK)

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            orders_qs = OrderService.create_from_cart(
                user,
                data['shipping_method'].id,
                data.get('address'),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serialized = self.get_serializer(orders_qs, many=True).data
        payload = {'orders': serialized}
        if cache_key:
            cache.set(cache_key, payload, timeout=3600)
        return Response(payload, status=status.HTTP_201_CREATED)