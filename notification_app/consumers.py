from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.exceptions import AuthenticationFailed

from users.authentication import JWTAuthMixin

import logging

logger = logging.getLogger("rest_framework")

class NotificationConsumer(JWTAuthMixin, AsyncJsonWebsocketConsumer):
    NOTIF_GROUP_TEMPLATE = "notifications_{user_id}"

    async def connect(self):
        try:
            self.user = await self.get_user_from_scope()
        except AuthenticationFailed:
            await self.close(code=4001)
            return

        self.group_name = self.NOTIF_GROUP_TEMPLATE.format(user_id=self.user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception as exc:
            logger.error("NotificationConsumer.disconnect failed for group %s: %s",
                         self.group_name, exc)

    async def notification_message(self, event):
        payload = event.get('payload')
        if not isinstance(payload, dict):
            return await self.send_json({
                'type': 'error',
                'detail': 'Malformed notification.'
            })
        await self.send_json({'type': 'notification.message', 'data': payload})