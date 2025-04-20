from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.exceptions import AuthenticationFailed
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model

from .models import Chat, Message


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Authenticate user via JWT in cookie
        try:
            self.user = await self.get_user_from_scope()
        except AuthenticationFailed:
            return await self.close(code=4001)

        # Load chat and check permissions
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat = await database_sync_to_async(get_object_or_404)(Chat, id=self.chat_id)
        if not (self.user == self.chat.buyer or 
                self.user == self.chat.owner or 
                self.user.is_staff):
            return await self.close(code=4003)

        # Join chat group
        self.group_name = f"chat_{self.chat_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Only handle message.send actions
        if content.get('type') != 'message.send':
            return

        text = content.get('text', '').strip()
        if not text:
            return

        # 1) Save the message
        message = await self.create_message(text)

        # 2) Broadcast to the chat group
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.message',
                'message': {
                    'id': message.id,
                    'sender_id': str(self.user.id),
                    'text': message.text,
                    'timestamp': message.timestamp.isoformat(),
                }
            }
        )

        # 3) Broadcast a notification to the recipient’s group
        recipient = self.chat.owner if self.user == self.chat.buyer else self.chat.buyer
        await self.channel_layer.group_send(
            f"notifications_{recipient.id}",
            {
                'type': 'notification.message',
                'payload': {
                    'chat_id': str(self.chat_id),
                    'sender_full_username': self.user.full_username,
                    'sender_avatar': self.user.avatar.url,
                    'message': message.text,
                    'timestamp': message.timestamp.isoformat(),
                }
            }
        )

    async def chat_message(self, event):
        # Forward chat messages to WebSocket
        await self.send_json({
            'type': 'message.new',
            'message': event['message']
        })

    @database_sync_to_async
    def get_user_from_scope(self):
        # Parse cookies
        headers = dict(self.scope.get("headers", []))
        raw_cookie = headers.get(b'cookie', b'').decode('utf-8')
        cookies = {}
        for pair in raw_cookie.split('; '):
            if '=' in pair:
                k, v = pair.split('=', 1)
                cookies[k] = v

        access_token = cookies.get("access_token")
        if not access_token:
            raise AuthenticationFailed({"code":"token_expired","message":"Access token missing."})

        # Decode token
        try:
            token = AccessToken(access_token)
            user_id = token.get("user_id")
            if not user_id:
                raise TokenError

            User = get_user_model()
            try:
                return User.objects.get(id=user_id)
            except ObjectDoesNotExist:
                raise AuthenticationFailed({"code":"invalid_token","message":"Invalid token."})

        except TokenError:
            raise AuthenticationFailed({"code":"token_expired","message":"Token expired."})
        except Exception:
            raise AuthenticationFailed({"code":"invalid_token","message":"Invalid token."})

    @database_sync_to_async
    def create_message(self, text):
        # Persist the new message
        return Message.objects.create(chat=self.chat, sender=self.user, text=text)
