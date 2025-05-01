from rest_framework import serializers
from users.models import User
from product_management.models import Product

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image
import io
import sys

class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing and updating the current user's profile.
    """
    class Meta:
        model = User
        fields = ['full_username', 'avatar', 'age', 'city', 'phone_number']
        read_only_fields = []
    

    def validate_avatar(self, avatar):

        if not avatar:
            return None

        # Check file type
        if not avatar.content_type.startswith("image"):
            raise serializers.ValidationError("Uploaded file is not an image.")

        # Check file size (10MB max)
        max_size_mb = 10
        if avatar.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Image size should not exceed {max_size_mb} MB.")

        try:
            # Open and optimize the image
            image = Image.open(avatar)
            image_format = image.format  # Preserve original format

            # Create a BytesIO stream to save optimized image
            output_io = io.BytesIO()
            image.save(output_io, format=image_format, optimize=True, quality=85)

            # Move the file pointer to the start
            output_io.seek(0)

            # Recreate a new InMemoryUploadedFile with the optimized image
            optimized_avatar = InMemoryUploadedFile(
                file=output_io,
                field_name="avatar",
                name=avatar.name,
                content_type=avatar.content_type,
                size=sys.getsizeof(output_io),
                charset=None
            )

            return optimized_avatar
        except Exception as e:
            raise serializers.ValidationError(f"Failed to process image: {str(e)}")

class BaseProductSerializer(serializers.ModelSerializer):
    feature_image = serializers.SerializerMethodField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)

    class Meta:
        fields = ['id','name','price','feature_image','stock','units_sold','average_rating']

    def get_feature_image(self, obj):
        media_qs = getattr(obj, 'feature_media', None) or obj.media.filter(is_feature=True)
        return media_qs[0].image.url if media_qs else None

class MyProductSerializer(BaseProductSerializer):
    class Meta(BaseProductSerializer.Meta):
        model = Product

class RecommendationSerializer(BaseProductSerializer):
    class Meta(BaseProductSerializer.Meta):
        model = Product