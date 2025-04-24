from rest_framework import serializers
from chat_app.models import Message

class NotificationSerializer(serializers.ModelSerializer):
    chat_id = serializers.CharField()
    sender_full_username = serializers.CharField(source='sender.full_username')
    sender_avatar = serializers.CharField(source='sender.avatar.url')
    message = serializers.CharField(source='text')

    class Meta:
        model = Message
        fields = [
            'id',
            'chat_id',
            'sender_full_username',
            'sender_avatar',
            'message',
            'timestamp',
            'is_read',
        ]
        read_only_fields = fields
