import os
from django.core.asgi import get_asgi_application
from core.settings.base import DEBUG  # Import DEBUG from the base settings

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from chat_app.routing import websocket_urlpatterns

# Use DEBUG to set the appropriate settings module for ASGI
if DEBUG:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')


from chat_app.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # HTTP -> Django
    "http": get_asgi_application(),

    # WebSocket -> Auth stack -> your chat URLRouter
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})