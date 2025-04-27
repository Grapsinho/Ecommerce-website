from rest_framework import serializers
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
        # first, see if view prefetched into .feature_media
        media_qs = getattr(obj.product, 'feature_media', None)
        # otherwise, fall back to querying the real manager
        if media_qs is None:
            media_qs = obj.product.media.filter(is_feature=True)
        if not media_qs:
            return None
        first = media_qs[0]
        return first.image.url if first.image else None

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_method = ShippingMethodSerializer(read_only=True)
    shipping_address = AddressSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'status', 'progress_percentage', 'expected_delivery_date',
            'shipping_method', 'shipping_address', 'shipping_fee', 'total_amount', 'items'
        ]