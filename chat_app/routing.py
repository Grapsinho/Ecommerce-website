from django.urls import path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chats/<uuid:chat_id>/", ChatConsumer.as_asgi()),
]