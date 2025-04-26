from rest_framework.response import Response
from rest_framework import status, permissions, viewsets, mixins
from rest_framework.decorators import action
from users.authentication import JWTAuthentication

from django.db.models import Prefetch

from .services import OrderService
from .serializers import OrderSerializer
from .models import Order, OrderItem
from .pagination import OrderCursorPagination
from product_management.models import ProductMedia


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


    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        """
        POST /orders/checkout/
        Payload must include 'shipping_method' and optional 'address' dict.
        Returns a list of newly created orders (one per seller).
        """
        try:
            orders_qs = OrderService.create_from_cart(
                request.user,
                request.data.get('shipping_method'),
                request.data.get('address'),
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(orders_qs, many=True)
        return Response({'orders': serializer.data}, status=status.HTTP_201_CREATED)