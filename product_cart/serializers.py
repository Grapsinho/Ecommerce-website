from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import CartItem, Cart
from product_management.models import Product

from drf_spectacular.utils import (
    extend_schema_serializer,
    OpenApiExample,
    extend_schema_field,
    OpenApiTypes
)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'CreateCartItem',
            summary='Add a product to the cart',
            request_only=True,
            value={'product_id': 42, 'quantity': 3}
        ),
        OpenApiExample(
            'CartItemResponse',
            summary='Example response for a cart item',
            response_only=True,
            value={
                'id': 1,
                'product_id': 42,
                'quantity': 3,
                'name': 'T-Shirt',
                'slug': 't-shirt',
                'feature_image_url': 'https://...jpg',
                'unit_price': '19.99'
            }
        )
    ]
)
class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    quantity = serializers.IntegerField(min_value=1)
    name = serializers.ReadOnlyField(source='product.name')
    slug = serializers.ReadOnlyField(source='product.slug')
    unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    feature_image_url = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id', 'product_id', 'quantity',
            'name', 'slug', 'feature_image_url', 'unit_price'
        ]

    @extend_schema_field(OpenApiTypes.URI)
    def get_feature_image_url(self, obj):
        featured = getattr(obj.product, 'featured_media', [])
        return featured[0].image.url if featured else None

    def validate(self, attrs):
        product = attrs.get('product', getattr(self.instance, 'product', None))
        qty = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        if product and qty and qty > product.stock:
            raise ValidationError({'quantity': 'Exceeds available stock.'})
        return attrs

    def create(self, validated_data):
        cart = self.context['request'].user.cart
        product = validated_data['product']
        quantity = validated_data['quantity']

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        if not created:
            if item.quantity + quantity > product.stock:
                raise ValidationError({'quantity': 'Exceeds available stock.'})
            item.quantity += quantity
            item.save(update_fields=['quantity'])
        return item

    def update(self, instance, validated_data):
        quantity = validated_data.get('quantity', instance.quantity)
        if quantity > instance.product.stock:
            raise ValidationError({'quantity': 'Exceeds available stock.'})
        instance.quantity = quantity
        instance.save(update_fields=['quantity'])
        return instance


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Cart
        fields = ['id', 'total_price', 'items']