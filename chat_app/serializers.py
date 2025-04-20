from rest_framework import serializers
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from product_management.models import Product
from .models import Chat, Message

User = get_user_model()


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

        # Fast path: avoid transaction if chat exists
        chat = Chat.objects.filter(buyer=buyer, owner=owner).first()
        if chat:
            if chat.product_id != product.id:
                chat.product = product
                chat.save(update_fields=['product', 'updated_at'])
            return chat

        # Slow path: create new chat
        try:
            with transaction.atomic():
                return Chat.objects.create(buyer=buyer, owner=owner, product=product)
        except IntegrityError:
            # someone else just created it
            return Chat.objects.get(buyer=buyer, owner=owner)


class ProductPreviewSerializer(serializers.Serializer):
    slug = serializers.SlugField(read_only=True)
    name = serializers.CharField(read_only=True)
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    condition = serializers.CharField(read_only=True)
    feature_image = serializers.SerializerMethodField()

    def get_feature_image(self, product):
        request = self.context.get('request')
        media_list = getattr(product, 'feature_media', [])
        if not media_list:
            return None
        url = media_list[0].image.url
        return request.build_absolute_uri(url) if request else url


class ChatListSerializer(serializers.ModelSerializer):
    with_user_full_username = serializers.SerializerMethodField()
    product = ProductPreviewSerializer(source='product', read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(source='unread', read_only=True)

    class Meta:
        model = Chat
        fields = [
            'id',
            'with_user_full_username',
            'product',
            'last_message',
            'unread_count'
        ]

    def get_with_user_full_username(self, obj):
        user = self.context['request'].user
        other = obj.get_other_user(user)
        return other.full_username

    def get_last_message(self, obj):
        if not hasattr(obj, 'last_text') or obj.last_text is None:
            return None
        return {'text': obj.last_text, 'timestamp': obj.last_ts}


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'chat', 'sender', 'text', 'timestamp']
        read_only_fields = ['id', 'chat', 'sender', 'timestamp']