from rest_framework import generics
from .models import Review
from product_management.models import Product
from .serializers import ReviewSerializer
from .permissions import IsOwnerOrAdmin
from users.authentication import JWTAuthentication

from rest_framework.pagination import LimitOffsetPagination

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

from rest_framework.permissions import SAFE_METHODS

class LoadMorePagination(LimitOffsetPagination):
    default_limit = 10

@extend_schema_view(
    get=extend_schema(
        summary="List Reviews",
        description="Retrieve a paginated list of reviews for a specific product. "
                    "Safe access without authentication."
    ),
    post=extend_schema(
        summary="Create Review",
        description="Submit a new review for a specific product. "
                    "Requires JWT authentication and the user must not have already reviewed the product."
    ),
)
class ReviewListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    pagination_class = LoadMorePagination
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwnerOrAdmin]

    def get_authenticators(self):
        if self.request and self.request.method in SAFE_METHODS:
            return []
        return super().get_authenticators()
    
    def get_queryset(self):
        slug = self.kwargs.get('slug')
        return Review.objects.filter(product__slug=slug).select_related('user').order_by('-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['product_slug'] = self.kwargs.get('slug')
        return context

    def perform_create(self, serializer):
        serializer.save()


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve Review",
        description="Retrieve a specific review by its ID without requiring authentication."
    ),
    patch=extend_schema(
        summary="Update Review",
        description="Update an existing review (only allowed for the review owner)."
    ),
    put=extend_schema(
        summary="Replace Review",
        description="Replace a review completely (only allowed for the review owner)."
    ),
    delete=extend_schema(
        summary="Delete Review",
        description="Delete a review (allowed for the review owner or an admin)."
    ),
)
class ReviewDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReviewSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwnerOrAdmin]
    lookup_field = 'id'
    lookup_url_kwarg = 'review_id'

    def get_authenticators(self):
        if self.request and self.request.method in SAFE_METHODS:
            return []
        return super().get_authenticators()

    def get_queryset(self):
        return Review.objects.select_related('user').all()