from rest_framework import serializers
from .models import User
from django.core.cache import cache
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image
import io
import sys


import logging

logger = logging.getLogger("rest_framework")

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=True,
        error_messages={
            "min_length": "Password must be at least 8 characters long.",
        }
    )
    
    class Meta:
        model = User
        
        fields = ('full_username', 'email', 'age', 'password', 'city', 'phone_number', 'avatar')
    
    def validate_email(self, value):
        value = value.lower()
        # Check if the email was confirmed
        confirmed_key = f"email_confirmed_{value}"
        if not cache.get(confirmed_key):
            logger.warning(f"Registration attempt with unconfirmed email: {value}")
            raise serializers.ValidationError("Email not confirmed. Please confirm your email before registering.")
        return value
    
    def validate_avatar(self, avatar):
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

    def create(self, validated_data):
        try:

            user = User.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password'],
                username=validated_data['username'],
                age=validated_data.get('age'),
                city=validated_data.get('city'),
                phone_number=validated_data.get('phone_number'),
                avatar=validated_data.get('avatar'),
            )
            logger.info(f"User {user.email} created successfully.")
            
            # Clear the confirmation flag after successful registration
            cache.delete(f"email_confirmed_{validated_data.get('email')}")
            return user
        except IntegrityError as ie:
            logger.error(f"Integrity error for {validated_data.get('email')}: {str(ie)}")
            raise serializers.ValidationError({"detail": "This email or username already exists."})
        except Exception as e:
            logger.error(f"Error creating user {validated_data.get('email')}: {str(e)}")
            raise serializers.ValidationError({"detail": "Failed to create user. Please try again."})
    
class LoginUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password."}
            )
        attrs['user'] = user  # Pass the authenticated user to the view
        return attrs

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        token = attrs.get('token')
        user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError("Invalid email address.")
        
        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            raise serializers.ValidationError("Invalid or expired token.")
        
        return attrs

    def save(self):
        email = self.validated_data['email']
        new_password = self.validated_data['new_password']
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'full_username', 'avatar', 'age', 'city', 'phone_number', 'created_at'
        )