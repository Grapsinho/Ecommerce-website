from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Prefetch

from product_management.models import Product, ProductMedia
from .models import Wishlist, WishlistItem
from .serializers import WishlistSerializer
from users.authentication import JWTAuthentication

class WishlistRetrieveAPIView(generics.RetrieveAPIView):
    """
    GET /wishlist/ — Retrieve or create the current user's wishlist.
    """
    serializer_class = WishlistSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

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
        # We know exactly one Wishlist exists per user—just grab it (or 404 if something's very wrong)
        return self.get_queryset().get()


class WishlistAddProductAPIView(APIView):
    """
    POST /wishlist/add/ — Add a product to the wishlist.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({"product_id": ["This field is required."]},
                            status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, id=product_id, is_active=True)
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)

        # Attempt to create; if it exists, catch the integrity error
        try:
            WishlistItem.objects.create(wishlist=wishlist, product=product)
        except Exception as e:
            # could be a UniqueConstraint violation
            return Response(
                {"detail": "Product already in wishlist."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = WishlistSerializer(
            Wishlist.objects.prefetch_related('items'),  # minimal prefetch
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class WishlistRemoveProductAPIView(APIView):
    """
    DELETE /wishlist/remove/ — Remove a product from the wishlist.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def delete(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({"product_id": ["This field is required."]},
                            status=status.HTTP_400_BAD_REQUEST)

        wishlist = get_object_or_404(Wishlist, user=request.user)
        item = WishlistItem.objects.filter(wishlist=wishlist, product__id=product_id).first()
        if not item:
            return Response(
                {"detail": "Product not found in your wishlist."},
                status=status.HTTP_404_NOT_FOUND
            )

        item.delete()
        serializer = WishlistSerializer(
            Wishlist.objects.prefetch_related('items'),
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)