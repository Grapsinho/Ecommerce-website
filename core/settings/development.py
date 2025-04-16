from .base import *

ALLOWED_HOSTS = ['*']

# installed apps
INSTALLED_APPS.append("debug_toolbar")


# middlewares
MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")


# CORS

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
]


# For django debug toolbar

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]