from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Authenticate via JWT in cookies
        try:
            self.user = await self.get_user_from_scope()
        except AuthenticationFailed:
            return await self.close(code=4001)

        # Join their personal notifications group
        self.group_name = f"notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_message(self, event):
        # Simply forward the payload to the client
        await self.send_json({
            'type': 'notification.message',
            'data': event['payload']
        })

    @database_sync_to_async
    def get_user_from_scope(self):
        # (Copy your JWT parsing code here)
        headers = dict(self.scope.get("headers", []))
        raw_cookie = headers.get(b'cookie', b'').decode()
        cookies = {k: v for k, v in (pair.split('=',1) for pair in raw_cookie.split('; ') if '=' in pair)}
        access_token = cookies.get("access_token")
        if not access_token:
            raise AuthenticationFailed({"code":"token_expired","message":"Access token missing."})

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
        except:
            raise AuthenticationFailed({"code":"invalid_token","message":"Invalid token."})
