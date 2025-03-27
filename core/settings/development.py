from .base import *

ALLOWED_HOSTS = ['*']

# installed apps
INSTALLED_APPS.append("debug_toolbar")


# middlewares
MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")


# CORS
CORS_ALLOW_ALL_ORIGINS = True


# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# For django debug toolbar

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]