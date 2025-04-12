import io
import base64
import imghdr

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from users.models import User
from .models import Product, ProductMedia, Category
from utils.image_opt import optimize_image

# ---------------------------
# Custom Image Field
# ---------------------------

class Base64ImageField(serializers.ImageField):
    """
    Accepts base64-encoded images, validates type and size,
    optimizes image, and returns a Django-compatible file object.
    
    Business Rules:
    - Only jpeg, jpg, png, gif types allowed
    - Max size: 10MB
    - Optimizes image before saving
    """
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                decoded_file = base64.b64decode(data)
            except Exception:
                self.fail("invalid_image")

            if len(decoded_file) > self.MAX_SIZE:
                raise ValidationError("Image size should not exceed 10 MB.")

            file_extension = imghdr.what(None, decoded_file)
            if file_extension not in ['jpeg', 'jpg', 'png', 'gif']:
                raise ValidationError("Unsupported image type. Please use jpeg, jpg, png, or gif.")

            temp_file = io.BytesIO(decoded_file)
            temp_file.name = f"temp.{file_extension}"
            temp_file.seek(0)

            try:
                optimized_file = optimize_image(temp_file)
            except Exception as e:
                raise ValidationError(f"Failed to optimize image: {str(e)}")

            data = optimized_file

        return super().to_internal_value(data)


# ---------------------------
# Category Serializer
# ---------------------------

class CategorySerializer(serializers.ModelSerializer):

    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent"]
    
    def get_children(self, obj):
        # Recursively serialize children if any exist
        if obj.get_children():
            serializer = CategorySerializer(obj.get_children(), many=True)
            return serializer.data
        return []


# ---------------------------
# Seller Serializer
# ---------------------------

class SellerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_username', 'phone_number', 'city']


# ---------------------------
# Product Media Serializers
# ---------------------------

class ProductMediaWriteSerializer(serializers.Serializer):
    """
    Serializer for uploading product images (write only).
    Uses Base64 for input and ensures only one featured image per product.
    """
    image = Base64ImageField()
    is_feature = serializers.BooleanField(default=False)

    def validate(self, data):
        if not data.get("image"):
            raise serializers.ValidationError("No image data submitted.")
        return data


class ProductMediaSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for displaying product media.
    """
    class Meta:
        model = ProductMedia
        fields = ['id', 'image', 'is_feature', 'created_at']


# ---------------------------
# Product Write Serializer
# ---------------------------

class ProductWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating products.
    Accepts nested image data and validates image count & featured image rules.
    """
    images = ProductMediaWriteSerializer(many=True, required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock',
            'condition', 'category', 'images'
        ]
        read_only_fields = ['id']

    def validate_price(self, value):
        if value <= 0.1:
            raise serializers.ValidationError("Price must be greater than $0.1.")
        return value

    def validate_stock(self, value):
        if value < 1:
            raise serializers.ValidationError("Stock must be greater than 1.")
        return value

    def validate_images(self, value):
        if sum(1 for img in value if img.get('is_feature', False)) > 1:
            raise serializers.ValidationError("Only one image can be marked as featured.")
        if len(value) > 6:
            raise serializers.ValidationError("A product cannot have more than 6 images.")
        return value

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        with transaction.atomic():
            product = Product.objects.create(**validated_data)
            if images_data:
                for image_data in images_data:
                    ProductMedia.objects.create(product=product, **image_data)
            else:
                # Create default media if no images are provided
                ProductMedia.objects.create(product=product)
        return product

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if images_data is not None:
                # Delete old media
                for media in instance.media.all():
                    try:
                        media.image.delete(save=False)
                    except Exception as e:
                        raise ValidationError(f"Error deleting image for media {media.pk}: {str(e)}")
                    media.delete()

                # Create new media
                for image_data in images_data:
                    ProductMedia.objects.create(product=instance, **image_data)
        return instance


# ---------------------------
# Product Read Serializer
# ---------------------------

class ProductRetrieveSerializer(serializers.ModelSerializer):
    """
    Serializer for returning product details with nested images,
    seller info, and category breadcrumb.
    """
    images = ProductMediaSerializer(source='media', many=True, read_only=True)
    seller = SellerSerializer(read_only=True)
    category_breadcrumb = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'slug', 'price', 'stock', 'condition',
            'images', 'category_breadcrumb', 'seller', 'created_at'
        ]

    def get_category_breadcrumb(self, obj):
        """
        Builds full breadcrumb path for the category.
        """
        parts = []
        category = obj.category
        while category:
            parts.append(category.name)
            category = category.parent
        return " > ".join(reversed(parts))


class ProductListSerializer(serializers.ModelSerializer):
    images = ProductMediaSerializer(source='media', many=True, read_only=True)
    seller = SellerSerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'slug', 'price', 'stock', 'condition',
            'images', 'seller', 'created_at'
        ]