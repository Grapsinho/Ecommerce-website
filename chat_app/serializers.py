from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model
from product_management.models import Product
from .models import Chat, Message

from drf_spectacular.utils import extend_schema_field, OpenApiTypes

User = get_user_model()


# for documentation
class LastMessageSerializer(serializers.Serializer):
    text = serializers.CharField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)

class OtherUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_username = serializers.CharField(read_only=True)
    avatar = serializers.URLField(read_only=True)
    city = serializers.CharField(read_only=True)


class ChatCreateSerializer(serializers.ModelSerializer):
    product_slug = serializers.SlugRelatedField(
        slug_field='slug',
        queryset=Product.objects.all(),
        write_only=True
    )

    class Meta:
        model = Chat
        fields = ['id', 'product_slug']
        read_only_fields = ['id']

    def validate(self, data):
        user = self.context['request'].user
        product = data['product_slug']
        if user == product.seller:
            raise serializers.ValidationError("Cannot start a chat with yourself.")
        return data

    def create(self, validated_data):
        buyer = self.context['request'].user
        product = validated_data['product_slug']
        owner = product.seller
        with transaction.atomic():
            chat, created = Chat.objects.get_or_create(
                buyer=buyer,
                owner=owner,
                defaults={'product': product}
            )
            if not created and chat.product_id != product.id:
                chat.product = product
                chat.save(update_fields=['product', 'updated_at'])
        return chat


class ProductPreviewSerializer(serializers.Serializer):
    slug = serializers.SlugField(read_only=True)
    name = serializers.CharField(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    condition = serializers.CharField(read_only=True)
    feature_image = serializers.SerializerMethodField()

    @extend_schema_field(
        OpenApiTypes.URI
    )
    def get_feature_image(self, product):
        featured = getattr(product, 'feature_media', [])
        if not featured:
            return None
        return featured[0].image.url


class ChatListSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    product = ProductPreviewSerializer(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'other_user', 'product', 'last_message', 'unread_count']

    @extend_schema_field(
        OtherUserSerializer
    )
    def get_other_user(self, obj):
        user = self.context['request'].user
        other = obj.owner if obj.buyer == user else obj.buyer
        avatar_url = other.avatar.url
        request = self.context.get('request')
        if request:
            avatar_url = request.build_absolute_uri(avatar_url)
        return {
            'id': other.id,
            'full_username': other.full_username,
            'avatar': avatar_url,
            'city': other.city,
        }

    @extend_schema_field(
        LastMessageSerializer
    )
    def get_last_message(self, obj):
        text = getattr(obj, 'last_message_text', None)
        ts = getattr(obj, 'last_message_timestamp', None)
        if text is None or ts is None:
            return None
        return {'text': text, 'timestamp': ts}


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.UUIDField(source='sender.id', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'chat', 'sender_id', 'text', 'timestamp']
        read_only_fields = ['id', 'chat', 'sender_id', 'timestamp']