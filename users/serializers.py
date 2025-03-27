from rest_framework import serializers
from .models import User
from django.core.cache import cache

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
        
        fields = ('username', 'email', 'age', 'password', 'city', 'phone_number', 'avatar')
    
    def validate_email(self, value):
        value = value.lower()
        # Check if the email was confirmed
        confirmed_key = f"email_confirmed_{value}"
        if not cache.get(confirmed_key):
            logger.warning(f"Registration attempt with unconfirmed email: {value}")
            raise serializers.ValidationError("Email not confirmed. Please confirm your email before registering.")
        return value

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
        except Exception as e:
            logger.error(f"Error creating user {validated_data.get('email')}: {str(e)}")
            raise serializers.ValidationError({"detail": "Failed to create user. Please try again."})