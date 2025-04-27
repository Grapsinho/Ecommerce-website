from rest_framework.response import Response
from rest_framework import status, permissions, viewsets, mixins
from rest_framework.decorators import action
from users.authentication import JWTAuthentication

from django.core.cache import cache
from django.db.models import Prefetch

from .services import OrderService
from .serializers import OrderSerializer, CheckoutSerializer, AddressSerializer
from .models import Order, OrderItem
from .pagination import OrderCursorPagination
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
    serializer_class = OrderSerializer
    pagination_class = OrderCursorPagination

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user, items__isnull=False)
                .select_related('shipping_method', 'shipping_address')
                .prefetch_related(
                     Prefetch('items', queryset=OrderItem.objects
                         .select_related('product', 'product__seller')
                         .prefetch_related(
                             Prefetch('product__media', ProductMedia.objects.filter(is_feature=True), 'feature_media')
                         )
                     )
                 )
                .distinct()
                .order_by('-created_at')
        )

    @action(detail=False, methods=['get'], url_path='default-address')
    def default_address(self, request):
        """
        GET /orders/default-address/
        Returns the user's saved address (or null), so the client can pre-fill
        the delivery form when they pick 'city' or 'regional' shipping.
        """
        user = request.user
        if hasattr(user, 'address'):
            return Response(AddressSerializer(user.address).data)
        return Response(None, status=status.HTTP_204_NO_CONTENT)


    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        """
        Idempotent checkout: requires client to send an Idempotency-Key header.
        If they retry with the same key, we'll return the same response
        (without creating new orders).
        """
        user = request.user

        # 1) Idempotency key handling
        idem_key = request.headers.get('Idempotency-Key')
        cache_key = None
        if idem_key:
            cache_key = f"checkout:{user.id}:{idem_key}"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached, status=status.HTTP_200_OK)

        # 2) Validate payload
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 3) Delegate to service (atomic inside)
        try:
            orders_qs = OrderService.create_from_cart(
                user,
                data['shipping_method'].id,
                data.get('address'),
            )
        except ValueError as exc:
            # Any failure (e.g. out-of-stock, own-product, missing address)
            # rolls back *all* writes, and we return an error to client
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4) Serialize & cache the response for idempotency
        serialized = OrderSerializer(orders_qs, many=True).data
        payload = {'orders': serialized}

        if cache_key:
            cache.set(cache_key, payload, timeout=3600)

        return Response(payload, status=status.HTTP_201_CREATED)