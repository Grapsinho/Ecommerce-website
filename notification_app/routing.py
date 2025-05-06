from django.urls import path
from .consumers import NotificationConsumer

from django.conf import settings

websocket_urlpatterns = [
    path(f'{settings.WS_PATH}/notifications/', NotificationConsumer.as_asgi()),
]