from django.urls import path
from .consumers import ChatConsumer

from django.conf import settings

websocket_urlpatterns = [
    path(f"{settings.WS_PATH}/chats/<uuid:chat_id>/", ChatConsumer.as_asgi()),
]