from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from rest_framework.exceptions import AuthenticationFailed
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model
from .models import Chat, Message
from django.shortcuts import get_object_or_404


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Authenticate user from JWT in cookie
        self.user = await self.get_user_from_scope()
        if self.user is None:
            return await self.close(code=4001)

        # Extract chat_id from URL route kwargs
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat = await database_sync_to_async(get_object_or_404)(Chat, id=self.chat_id)

        # Check permissions: participant or admin
        if not (self.user == self.chat.buyer or self.user == self.chat.owner or self.user.is_staff):
            return await self.close(code=4003)

        # Join group
        self.group_name = f"chat_{self.chat_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Expect {'type': 'message.send', 'text': '...'}
        msg_type = content.get('type')
        if msg_type == 'message.send':
            text = content.get('text', '').strip()
            if not text:
                return
            # Save message
            message = await self.create_message(text)
            # Broadcast to group
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

    async def chat_message(self, event):
        # Send new message to WebSocket
        await self.send_json({
            'type': 'message.new',
            'message': event['message']
        })

    @database_sync_to_async
    def get_user_from_scope(scope):
        # 1. Extract the Cookie header from the scope
        headers = dict(scope.get("headers", []))
        raw_cookie = headers.get(b'cookie', b'').decode('utf-8')

        # 2. Parse into a dict
        cookies = {}
        for pair in raw_cookie.split('; '):
            if '=' in pair:
                key, val = pair.split('=', 1)
                cookies[key] = val

        # 3. Pull out the JWT
        access_token = cookies.get("access_token")
        if not access_token:
            raise AuthenticationFailed({
                "code": "token_expired",
                "message": "Access token missing or expired. Please refresh your session."
            })

        # 4. Decode and validate
        try:
            token = AccessToken(access_token)
            user_id = token.get("user_id")
            if not user_id:
                raise TokenError

            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
            except ObjectDoesNotExist:
                raise AuthenticationFailed({
                    "code": "invalid_token",
                    "message": "Invalid or expired token. Please log in again."
                })

            return user

        except TokenError:
            raise AuthenticationFailed({
                "code": "token_expired",
                "message": "Access token expired. Please refresh your session."
            })
        except Exception:
            raise AuthenticationFailed({
                "code": "invalid_token",
                "message": "Invalid or expired token. Please log in again."
            })

    @database_sync_to_async
    def create_message(self, text):
        msg = Message.objects.create(chat=self.chat, sender=self.user, text=text)
        return msg
