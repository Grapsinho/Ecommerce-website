import json
from typing import List

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from users.models import User
from .models import Product, ProductMedia, Category
from utils.image_opt import process_uploaded_file, validate_uploaded_file


# ---------------------------
# Category Serializer
# ---------------------------

class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "children"]

    def get_children(self, obj: Category) -> List[dict]:
        # With cache_tree_children, children are already fetched.
        children = list(obj.children.all())
        if children:
            serializer = CategorySerializer(children, many=True)
            return serializer.data
        return []


class SimpleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent"]

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
    # Optional id to reference an existing image.
    id = serializers.IntegerField(required=False)
    # Change from Base64ImageField to the default ImageField.
    image = serializers.ImageField(required=False)
    is_feature = serializers.BooleanField(default=False)

    def validate(self, data):
        # If the incoming data contains an 'id', assume this is an existing image.
        # Otherwise, require that an image has been provided.
        if not data.get("id") and not data.get("image"):
            raise serializers.ValidationError("No image file was submitted.")
        # You can also add custom validations here (file type, size, etc.) if you want.
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
    # Remove the nested "images" field – files will be retrieved directly from request.FILES.
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock',
            'condition', 'category'
        ]
        read_only_fields = ['id', 'seller', 'slug', 'created_at', 'updated_at', 'units_sold']

    def validate_price(self, value):
        if value <= 0.1:
            raise serializers.ValidationError("Price must be greater than $0.1.")
        return value

    def validate_stock(self, value):
        if value < 1:
            raise serializers.ValidationError("Stock must be greater than 1.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        images = request.FILES.getlist('images')
        # Enforce mandatory images only for creation.
        if self.instance is None:
            if not images:
                raise ValidationError({"images": "At least one product image is required."})
            if len(images) > 6:
                raise ValidationError({"images": "A product cannot have more than 6 images."})
            for file in images:
                validate_uploaded_file(file)
        # For updates, new images are optional; if provided, validate them.
        elif images:
            if len(images) > 6:
                raise ValidationError({"images": "A product cannot have more than 6 images."})
            for file in images:
                validate_uploaded_file(file)
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        images_files = request.FILES.getlist('images')
        try:
            featured_index = int(request.data.get('featured_index', 0))
        except (ValueError, TypeError):
            featured_index = 0

        with transaction.atomic():
            product = Product.objects.create(**validated_data)
            for idx, file in enumerate(images_files):
                # Optimize the file only during creation.
                optimized_file = process_uploaded_file(file)
                is_feature = (idx == featured_index)
                ProductMedia.objects.create(product=product, image=optimized_file, is_feature=is_feature)
        return product

    def update(self, instance, validated_data):
        request = self.context.get('request')
        images_metadata_json = request.data.get('images_metadata')

        # If no images metadata is provided, assume the images remain unchanged.
        if not images_metadata_json:
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            return instance

        # Otherwise process images metadata for update.
        try:
            images_metadata = json.loads(images_metadata_json)
        except json.JSONDecodeError:
            raise ValidationError({"images_metadata": "Invalid JSON format."})

        new_images_files = request.FILES.getlist('images')
        new_file_pointer = 0

        # Build a dictionary of existing media.
        existing_media_dict = {media.id: media for media in instance.media.all()}

        # Process the metadata to update or add images.
        for meta in images_metadata:
            if 'id' in meta:
                # Update existing image.
                media_id = meta['id']
                media_obj = existing_media_dict.get(media_id)
                if media_obj:
                    media_obj.is_feature = meta.get('is_feature', False)
                    media_obj.save()
                    del existing_media_dict[media_id]
            elif 'index' in meta:
                # Add a new image.
                if new_file_pointer >= len(new_images_files):
                    raise ValidationError("Mismatch between new images metadata and files provided.")
                file = new_images_files[new_file_pointer]
                optimized_file = process_uploaded_file(file)
                is_feature = meta.get('is_feature', False)
                ProductMedia.objects.create(product=instance, image=optimized_file, is_feature=is_feature)
                new_file_pointer += 1
            else:
                raise ValidationError("Each images_metadata item must have either 'id' or 'index'.")

        # Delete any remaining (unreferenced) existing media.
        for media in existing_media_dict.values():
            try:
                media.image.delete(save=False)
            except Exception:
                pass
            media.delete()

        # Update non-image fields.
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

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

    def get_category_breadcrumb(self, obj: Product) -> str:
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

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'slug', 'price', 'stock', 'condition',
            'images', 'created_at'
        ]


class ProductDetailUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock',
            'condition', 'category', 'images'
        ]


class ProductUpdateRetrieveSerializer(serializers.ModelSerializer):
    """
    Serializer for returning minimal product info (for update) that includes:
      - Product details
      - Child category as a primary key
      - Images (nested)
      - Parent category slug as a computed field for loading category selections on the frontend.
    """
    images = ProductMediaSerializer(source='media', many=True, read_only=True)
    # Return category as a primary key (child category id)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    # Provide parent's slug for use in UI to load parent categories
    category_parent_slug = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock',
            'condition', 'category', 'images', 'category_parent_slug'
        ]

    def get_category_parent_slug(self, obj: Product) -> str:
        """
        Returns the slug of the parent category of the product's category.
        If no parent exists, returns None.
        """
        if obj.category and obj.category.parent:
            return obj.category.parent.slug
        return None