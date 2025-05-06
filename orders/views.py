from rest_framework import permissions, viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, extend_schema_view
from users.authentication import JWTAuthentication
from .serializers import (
    OrderSerializer, OrderDetailSerializer,
    CheckoutSerializer, AddressSerializer
)
from .models import Order
from .services import OrderService
from .ord_cache import get_cached_order_ids
from .ord_utils import get_pagination_params, build_order_queryset, build_page_urls

import logging
logger = logging.getLogger("rest_framework")


@extend_schema_view(
    list=extend_schema(
        summary="List Orders",
        description="Retrieve a paginated list of your orders.",
        responses={200: OrderSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Retrieve Order",
        description="Retrieve detailed information for a single order, including milestones and progress.",
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                description="UUID of the order",
                required=True,
                type=OpenApiTypes.UUID,
            )
        ],
        responses={200: OrderDetailSerializer}
    ),
    default_address=extend_schema(
        summary="Get Default Address",
        description="Returns the user's saved shipping address or HTTP 204 if none.",
        responses={200: AddressSerializer, 204: None}
    ),
    checkout=extend_schema(
        summary="Checkout Cart",
        description=(
            "Idempotent checkout endpoint that converts cart items into orders. "
            "Supply `Idempotency-Key` header to retry without duplication."
        ),
        request=CheckoutSerializer,
        responses={201: OrderDetailSerializer, 400: OpenApiTypes.OBJECT}
    )
)
class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if self.request and self.action == 'list':
            order_ids = get_cached_order_ids(user)
            # build_order_queryset should return an Order queryset
            return build_order_queryset(order_ids)
        # retrieve, etc.
        return Order.objects.filter(user=user)

    def get_serializer_class(self):
        return OrderDetailSerializer if self.request and self.action == 'retrieve' else OrderSerializer

    def list(self, request, *args, **kwargs):
        # Reuse get_queryset for the un‐paginated base set:
        base_qs = self.get_queryset()
        total = base_qs.count()

        page, page_size = get_pagination_params(request)
        start, end = (page - 1) * page_size, page * page_size
        page_qs = base_qs[start:end]

        data = self.get_serializer(page_qs, many=True).data
        next_url, prev_url = build_page_urls(request, page, page_size, total)

        return Response({
            'count': total,
            'next': next_url,
            'previous': prev_url,
            'results': data,
        })

    @action(detail=False, methods=['get'], url_path='default-address')
    def default_address(self, request):
        if hasattr(request.user, 'address'):
            return Response(AddressSerializer(request.user.address).data)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        user = request.user
        idem = request.headers.get('Idempotency-Key')
        cache_key = f"checkout:{user.id}:{idem}" if idem else None

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

        serialized = OrderDetailSerializer(orders_qs, many=True).data
        payload = {'orders': serialized}

        if cache_key:
            cache.set(cache_key, payload, timeout=3600)
        return Response(payload, status=status.HTTP_201_CREATED)