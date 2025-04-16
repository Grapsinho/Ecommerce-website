from rest_framework import serializers
from .models import Review
from users.models import User

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
        if value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be between 0 and 5.")
        return value

    def validate(self, data):
        request = self.context.get('request')
        product = self.context.get('product')
        # If creating a new review, ensure the user hasn't already reviewed the product.
        if request.method == 'POST':
            if Review.objects.filter(product=product, user=request.user).exists():
                raise serializers.ValidationError("You have already reviewed this product.")
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        # Set user from the request and product from the context.
        validated_data['user'] = request.user
        validated_data['product'] = self.context.get('product')
        return super().create(validated_data)