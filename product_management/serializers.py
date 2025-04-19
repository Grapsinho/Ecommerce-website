import json
from typing import List

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from users.models import User
from .models import Product, ProductMedia, Category
from utils.image_opt import process_uploaded_file, validate_uploaded_file

import logging

logger = logging.getLogger("rest_framework")


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
    # Remove nested "images" field – files are handled via request.FILES.
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
        if self.instance is None:
            # Creation requires at least one image and no more than 6.
            if not images:
                raise ValidationError({"images": "At least one product image is required."})
            if len(images) > 6:
                raise ValidationError({"images": "A product cannot have more than 6 images."})
            for file in images:
                validate_uploaded_file(file)
        else:
            # On update, if new images are provided, validate the count and each file.
            if images and len(images) > 6:
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
                optimized_file = process_uploaded_file(file)
                is_feature = (idx == featured_index)
                ProductMedia.objects.create(product=product, image=optimized_file, is_feature=is_feature)
        return product

    def update(self, instance, validated_data):
        request = self.context.get('request')
        images_metadata_json = request.data.get('images_metadata')

        try:
            with transaction.atomic():
                self._apply_validated_fields(instance, validated_data)

                if images_metadata_json:
                    metadata = self._parse_images_metadata(images_metadata_json)
                    self._update_product_images(instance, metadata, request)
            return instance
        except Exception as exc:
            logger.exception('Error updating Product ID %s: %s', instance.id, exc)
            raise

    def _apply_validated_fields(self, instance, validated_data):
        """
        Apply updated fields from validated_data onto the instance and save.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

    def _parse_images_metadata(self, images_metadata_json):
        """
        Validate and parse the images_metadata JSON.
        """
        try:
            metadata = json.loads(images_metadata_json)
        except json.JSONDecodeError as e:
            raise ValidationError({
                "images_metadata": f"Invalid JSON: {str(e)}. Please ensure the value is a properly formatted JSON list."
            })

        if not isinstance(metadata, list):
            raise ValidationError({
                "images_metadata": "Expected a list of metadata dictionaries, got something else."
            })
        return metadata

    def _update_product_images(self, instance, metadata, request):
        new_images_files = request.FILES.getlist('images')
        new_file_index = 0
        # Build a dict of current media for quick lookup.
        existing_media = {media.id: media for media in instance.media.all()}

        for idx, meta in enumerate(metadata):
            if not isinstance(meta, dict):
                raise ValidationError({"images_metadata": f"Metadata item at index {idx} is not valid."})

            if 'id' in meta:
                media_id = meta.get('id')
                media_obj = existing_media.get(media_id)
                if not media_obj:
                    raise ValidationError({"images_metadata": f"No existing image with id {media_id} found."})
                media_obj.is_feature = meta.get('is_feature', False)
                media_obj.save()
                # Remove processed media.
                existing_media.pop(media_id)
                
            elif 'index' in meta:
                if new_file_index >= len(new_images_files):
                    raise ValidationError({"images_metadata": "Mismatch between images_metadata and uploaded files."})
                file = new_images_files[new_file_index]
                optimized_file = process_uploaded_file(file)
                is_feature = meta.get('is_feature', False)
                ProductMedia.objects.create(product=instance, image=optimized_file, is_feature=is_feature)
                new_file_index += 1
            else:
                raise ValidationError({"images_metadata": "Each metadata item must include either 'id' or 'index'."})

        # Delete any existing media not referenced in metadata.
        # But only delete if deletion won't remove all images.
        for media_obj in list(existing_media.values()):
            if instance.media.count() - 1 <= 0:
                # Prevent deletion that would remove the last image.
                raise ValidationError({"images": "A product must have at least one image."})
            try:
                media_obj.image.delete(save=False)
            except Exception as e:
                logger.warning('Failed to delete image for ProductMedia ID %s: %s', media_obj.id, e)

            media_obj.delete()

        if new_file_index < len(new_images_files):
            raise ValidationError({"images": "There are more uploaded files than metadata instructions provided."})



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
            'images', 'category_breadcrumb', 'seller', 'created_at', "average_rating", "total_reviews"
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
            'images', 'created_at', "average_rating"
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