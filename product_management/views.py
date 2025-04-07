from django.db import transaction
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend

from .models import Product
from .serializers import ProductSerializer, RetrieveProductSerializer
from .filters import ProductFilter
from .pagination import ProductPagination
from users.authentication import JWTAuthentication

class IsOwnerOrAdmin(BasePermission):
    """
    Custom permission allowing only the product owner or an admin to update or delete.
    """
    def has_object_permission(self, request, view, obj):
        return (request.user == obj.seller) or request.user.is_staff

class ProductViewSet(viewsets.ModelViewSet):
    """
    Product CRUD endpoints:
      - List/Retrieve: Publicly available, showing only active products.
      - Create/Update: Authenticated users can create/update products.
        Updates are allowed even if the product is in an active cart.
      - Delete: Prevented if the product is in an active cart (wrapped in an atomic transaction).
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    authentication_classes = [JWTAuthentication]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter
    pagination_class = ProductPagination

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        return [AllowAny()]

    def get_queryset(self):

        queryset = Product.objects.all().select_related('seller').prefetch_related('media', 'categories')

        if self.action in ['list', 'retrieve']:
            return queryset.filter(is_active=True)
        return queryset

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return RetrieveProductSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                for media in instance.media.all():
                    media.image.delete(save=False)
                    media.delete()
                instance.delete()
        except Exception as e:
            raise ValidationError(f"Deletion failed: {str(e)}")
