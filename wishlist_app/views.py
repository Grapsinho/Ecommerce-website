from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Prefetch

from drf_spectacular.utils import (
    extend_schema, OpenApiResponse
)

from product_management.models import Product, ProductMedia
from .models import Wishlist, WishlistItem
from .serializers import WishlistSerializer, WishlistActionSerializer
from users.authentication import JWTAuthentication


class WishlistRetrieveAPIView(generics.RetrieveAPIView):
    """
    GET /wishlist/ — Retrieve the current user's wishlist.
    Returns all wishlist items with simplified product details, including the featured image URL.
    """
    serializer_class = WishlistSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: WishlistSerializer},
        description=(
            "Fetch the authenticated user's wishlist. "
            "Each item includes product ID, name, description, price, stock, and `feature_image` URL."
        )
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # Prefetch items → product → featured media into `prefetched_feature`
        return (
            Wishlist.objects.filter(user=self.request.user)
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=(
                        WishlistItem.objects.select_related('product')
                        .prefetch_related(
                            Prefetch(
                                'product__media',
                                queryset=ProductMedia.objects.filter(is_feature=True),
                                to_attr='prefetched_feature'
                            )
                        )
                    )
                )
            )
        )

    def get_object(self):
        # Guaranteed to exist via signup signal; `.get()` will 404 on serious errors
        return self.get_queryset().get()


class WishlistAddProductAPIView(APIView):
    """
    POST /wishlist/add/ — Add a product to the wishlist.
    Body: { "product_id": <int> }
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=WishlistActionSerializer,
        responses={
            201: OpenApiResponse(description="Wishlist returned with new item"),
            400: OpenApiResponse(description="Product already in wishlist or invalid product_id"),
            404: OpenApiResponse(description="Product not found or inactive"),
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = WishlistActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_id = serializer.validated_data['product_id']

        product = get_object_or_404(Product, id=product_id, is_active=True)
        wishlist = Wishlist.objects.get(user=request.user)

        try:
            WishlistItem.objects.create(wishlist=wishlist, product=product)
        except Exception:
            return Response(
                {"detail": "Product already in wishlist."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Return updated wishlist
        serializer = WishlistSerializer(wishlist, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WishlistRemoveProductAPIView(APIView):
    """
    DELETE /wishlist/remove/ — Remove a product from the wishlist.
    Body: { "product_id": <int> }
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=WishlistActionSerializer,
        responses={
            200: OpenApiResponse(description="Wishlist returned without removed item"),
            404: OpenApiResponse(description="Product not found in wishlist"),
        },
    )
    @transaction.atomic
    def delete(self, request):
        serializer = WishlistActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_id = serializer.validated_data['product_id']

        wishlist = get_object_or_404(Wishlist, user=request.user)
        try:
            item = WishlistItem.objects.get(wishlist=wishlist, product__id=product_id)
        except WishlistItem.DoesNotExist:
            return Response(
                {"detail": "Product not found in your wishlist."},
                status=status.HTTP_404_NOT_FOUND
            )

        item.delete()
        serializer = WishlistSerializer(wishlist, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)