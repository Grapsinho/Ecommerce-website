from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework.exceptions import AuthenticationFailed

from .models import Chat, Message
from users.authentication import JWTAuthMixin

import logging

logger = logging.getLogger("rest_framework")


class ChatConsumer(JWTAuthMixin, AsyncJsonWebsocketConsumer):
    # DRY’d group‐name templates
    CHAT_GROUP_TEMPLATE = "chat_{chat_id}"
    NOTIF_GROUP_TEMPLATE = "notifications_{user_id}"

    @database_sync_to_async
    def fetch_chat(self, chat_id):
        return Chat.objects.select_related('buyer', 'owner').get(id=chat_id)

    async def connect(self):
        # 1) authenticate
        try:
            self.user = await self.get_user_from_scope()
        except AuthenticationFailed:
            await self.close(code=4001)
            return

        # 2) load chat
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        try:
            self.chat = await self.fetch_chat(self.chat_id)
        except Chat.DoesNotExist:
            await self.close(code=4004)
            return

        # 3) permission check
        if not (self.user in (self.chat.buyer, self.chat.owner) or self.user.is_staff):
            await self.close(code=4003)
            return

        # 4) join group
        self.group_name = self.CHAT_GROUP_TEMPLATE.format(chat_id=self.chat_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # at least log on failure
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception as exc:
            logger.error("ChatConsumer.disconnect failed for group %s: %s",
                         self.group_name, exc)

    async def receive_json(self, content, **kwargs):
        if content.get('type') != 'message.send':
            return await self.send_json({'type': 'error', 'detail': 'Unsupported action.'})

        text = content.get('text', '').strip()
        if not text:
            return await self.send_json({'type': 'error', 'detail': 'Empty message.'})

        # 1) Save the message
        try:
            message = await self.create_message(text)
        except Exception as e:
            return await self.send_json({'type': 'error', 'detail': f'Could not save message. {e}'})

        payload = {
            'id': str(message.id),
            'chat_id': str(self.chat_id),
            'sender_id': str(self.user.id),
            'text': message.text,
            'timestamp': message.timestamp.isoformat(),
        }

        # 2) Broadcast to chat group
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'chat.message', 'message': payload}
        )

        # 3) Notify the other user
        recipient = self.chat.owner if self.user == self.chat.buyer else self.chat.buyer
        notif_group = self.NOTIF_GROUP_TEMPLATE.format(user_id=recipient.id)
        await self.channel_layer.group_send(
            notif_group,
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
        await self.send_json({'type': 'message.new', 'message': event['message']})

    async def message_deleted(self, event):
        await self.send_json({'type': 'message.deleted', 'message_id': event['message_id']})

    @database_sync_to_async
    def create_message(self, text):
        return Message.objects.create(chat=self.chat, sender=self.user, text=text)