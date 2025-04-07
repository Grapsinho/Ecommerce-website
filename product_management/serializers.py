import io
import sys
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from users.models import User
from rest_framework import serializers
from .models import Product, ProductMedia, Category
from django.db import transaction
from rest_framework.exceptions import ValidationError

class SellerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_username', 'phone_number', 'city']

class ProductMediaCreateSerializer(serializers.Serializer):
    image = serializers.ImageField()
    is_feature = serializers.BooleanField(required=False, default=False)

    def validate_image(self, image):

        if not image:
            return None

        if not image.content_type.startswith("image"):
            raise serializers.ValidationError("Uploaded file is not an image.")

        max_size_mb = 10
        if image.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Image size should not exceed {max_size_mb} MB.")

        try:
            img = Image.open(image)
            image_format = img.format

            output_io = io.BytesIO()
            img.save(output_io, format=image_format, optimize=True, quality=85)
            output_io.seek(0)

            optimized_image = InMemoryUploadedFile(
                file=output_io,
                field_name="image",
                name=image.name,
                content_type=image.content_type,
                size=sys.getsizeof(output_io),
                charset=None
            )

            return optimized_image

        except Exception as e:
            raise serializers.ValidationError(f"Failed to process image: {str(e)}")

class ProductMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMedia
        fields = ['id', 'image', 'is_feature', 'created_at']

class ProductSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), many=True
    )
    images = ProductMediaCreateSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock', 'condition',
            'categories', 'images', 'slug', 'seller', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'seller', 'created_at', 'updated_at', 'is_active']

    def validate_price(self, value):
        if value <= 0.1:
            raise serializers.ValidationError("Price must be greater than $0.1.")
        return value

    def validate_stock(self, value):
        if value <= 1:
            raise serializers.ValidationError("Stock must be greater than 1.")
        return value

    def validate_images(self, images):
        feature_count = sum(1 for img in images if img.get('is_feature', False))
        if feature_count > 1:
            raise serializers.ValidationError("Only one image can be marked as featured.")
        if len(images) > 6:
            raise serializers.ValidationError("A product cannot have more than 6 images.")
        return images

    def validate(self, data):
        required_fields = ["name", "description", "price", "stock", "condition", "categories"]
        for field in required_fields:
            if field not in data or not data[field]:
                raise serializers.ValidationError({field: "This field is required."})
        return data

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        categories = validated_data.pop('categories')
        product = Product.objects.create(**validated_data)
        product.categories.set(categories)

        if images_data == []:
            ProductMedia.objects.create(product=product)

        for image_data in images_data:
            ProductMedia.objects.create(product=product, **image_data)
        return product

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', None)
        categories = validated_data.pop('categories', None)

        try:
            with transaction.atomic():
                # Update the product fields
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                instance.save()

                # Update categories if provided
                if categories is not None:
                    instance.categories.set(categories)

                # If images_data is provided, delete existing media and add new images
                if images_data is not None:
                    # Delete existing media files safely
                    for media in instance.media.all():
                        try:
                            media.image.delete(save=False)
                        except Exception as e:
                            raise ValidationError(f"Error deleting image file for media ID {media.pk}: {str(e)}")
                        media.delete()
                    
                    # Create new media entries
                    for image_data in images_data:
                        ProductMedia.objects.create(product=instance, **image_data)

        except Exception as e:
            raise ValidationError(f"Update failed: {str(e)}")
        return instance

class RetrieveProductSerializer(serializers.ModelSerializer):
    images = ProductMediaSerializer(source='media', many=True, read_only=True)
    seller = SellerSerializer(read_only=True)
    category_breadcrumb = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'name', 'description', 'slug', 'price', 'stock', 'condition',
            'images', 'category_breadcrumb', 'seller', 'created_at'
        ]

    def get_category_breadcrumb(self, obj):
        breadcrumbs = []
        for category in obj.categories.all():
            ancestors = category.get_ancestors(include_self=True)
            breadcrumb = " > ".join([ancestor.name for ancestor in ancestors])
            breadcrumbs.append(breadcrumb)
        return breadcrumbs
