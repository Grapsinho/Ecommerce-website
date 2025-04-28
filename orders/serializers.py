from rest_framework import serializers
from django.utils import timezone
from .models import Address, ShippingMethod, Order, OrderItem

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'street', 'city', 'region', 'postal_code']

class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = ['id', 'name', 'flat_fee', 'lead_time_min', 'lead_time_max']

class AddressInputSerializer(serializers.Serializer):
    street = serializers.CharField()
    city = serializers.CharField()
    region = serializers.CharField()
    postal_code = serializers.CharField()

class CheckoutSerializer(serializers.Serializer):
    shipping_method = serializers.PrimaryKeyRelatedField(
        queryset=ShippingMethod.objects.all()
    )
    address = AddressInputSerializer(required=False)

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    feature_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['product_name', 'quantity', 'unit_price', 'subtotal', 'feature_image']

    def get_feature_image(self, obj):
        media_qs = getattr(obj.product, 'feature_media', None)
        if media_qs is None:
            media_qs = obj.product.media.filter(is_feature=True)
        if not media_qs:
            return None
        return media_qs[0].image.url if media_qs[0].image else None

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_method = ShippingMethodSerializer(read_only=True)
    shipping_address = AddressSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'expected_delivery_date',
            'shipping_method', 'shipping_address',
            'shipping_fee', 'total_amount', 'items'
        ]

class OrderDetailSerializer(OrderSerializer):
    milestones = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['milestones', 'progress']

    def get_milestones(self, obj):
        start = obj.created_at
        min_delivery = start + obj.shipping_method.lead_time_min
        delivered = obj.expected_delivery_date
        return [
            {'name': 'Preparing',    'time': start},
            {'name': 'Min Delivery', 'time': min_delivery},
            {'name': 'Delivered',    'time': delivered},
        ]

    def get_progress(self, obj):
        now = timezone.now()
        start = obj.created_at
        end = obj.expected_delivery_date
        if now <= start:
            return 0
        if now >= end:
            return 100
        elapsed = (now - start).total_seconds()
        total = (end - start).total_seconds()
        return (elapsed / total) * 100