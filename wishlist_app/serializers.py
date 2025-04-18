from rest_framework import serializers
from product_management.models import Product
from .models import Wishlist, WishlistItem

class SimpleProductSerializer(serializers.ModelSerializer):
    feature_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'feature_image']

    def get_feature_image(self, obj):
        # Because we used to_attr='prefetched_feature', it's always a list
        featured_list = getattr(obj, 'prefetched_feature', None)
        if featured_list:
            # Grab the first (and only) featured media object
            return featured_list[0].image.url

        # Fallback to one‐off DB hit if something slipped through
        feat = obj.media.filter(is_feature=True).first()
        return feat.image.url if feat else None

class WishlistItemSerializer(serializers.ModelSerializer):
    product = SimpleProductSerializer(read_only=True)

    class Meta:
        model = WishlistItem
        fields = ['id', 'product', 'created_at']

class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'created_at', 'items']
        read_only_fields = ['created_at', 'items']