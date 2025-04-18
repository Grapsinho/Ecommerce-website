from rest_framework import serializers
from django.shortcuts import get_object_or_404
from .models import Review
from users.models import User
from product_management.models import Product

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'full_username', 'avatar')


class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'user', 'message', 'rating', 'created_at', 'updated_at')
        read_only_fields = ('user', 'created_at', 'updated_at')

    def validate_rating(self, value):
        if not (0 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 0 and 5.")
        return value

    def validate(self, data):
        request = self.context['request']
        slug = self.context['product_slug']
        # Only on create: ensure this user hasn’t already reviewed
        if request.method == 'POST':
            product = get_object_or_404(Product, slug=slug)
            if Review.objects.filter(product=product, user=request.user).exists():
                raise serializers.ValidationError("You have already reviewed this product.")
        return data

    def create(self, validated_data):
        request = self.context['request']
        slug = self.context['product_slug']
        product = get_object_or_404(Product, slug=slug)
        # set the FK fields
        validated_data['product'] = product
        validated_data['user'] = request.user
        return super().create(validated_data)