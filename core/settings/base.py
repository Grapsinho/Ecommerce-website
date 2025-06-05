from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv()

debug = os.environ.get('DEBUG')
secret_key = os.environ.get('KEY_SECRET')

WS_PATH = "ws"

SECRET_KEY = secret_key

if debug == "True":
    DEBUG = True
else:
    DEBUG = False
    WS_PATH = "wss"

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "daphne",

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # local apps
    "users.apps.UsersConfig",
    "product_management.apps.ProductManagementConfig",
    "review_rating.apps.ReviewRatingConfig",
    "wishlist_app.apps.WishlistAppConfig",
    "product_cart.apps.ProductCartConfig",
    "chat_app.apps.ChatAppConfig",
    "notification_app.apps.NotificationAppConfig",
    "orders.apps.OrdersConfig",
    "dashboard.apps.DashboardConfig",

    # external app
    "mptt",
    "django_filters",

    # third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',

    "corsheaders",

    # cloudinary apps
    "cloudinary",
    "cloudinary_storage",

    # documentation
    'drf_spectacular',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',

    # cors middleware
    "corsheaders.middleware.CorsMiddleware",

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

ASGI_APPLICATION = 'core.asgi.application'

# custom user
AUTH_USER_MODEL = "users.User"

# API Base configuration
REST_FRAMEWORK = {
    # Use JWT Authentication
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    # Use drf-spectacular for schema generation
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],

    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '35/minute',
        'email_confirmation': '3/minute',
        'chat_create': '10/min',
        'message_send': '20/min',
    },
}

# JWT token Base configuration

access_token_lifetime = os.environ.get("ACCESS_TOKEN_LIFETIME_MINUTES", 10)
refresh_token_lifetime = os.environ.get("REFRESH_TOKEN_LIFETIME_MINUTES", 20)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(access_token_lifetime)), # i will change these after im done with testing
    "REFRESH_TOKEN_LIFETIME": timedelta(minutes=int(refresh_token_lifetime)), # i will change these after im done with testing
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}


SPECTACULAR_SETTINGS = {
    'TITLE': 'Buy-Sell E-commerce',
    'DESCRIPTION': 'API documentation for the buy-sell E-commerce.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SECURITY': [{'JWTAuth': []}],
}


# redis for caching

redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")

redis_url_websocket = os.environ.get("REDIS_URL_WEBSOCKET", "redis://127.0.0.1:6379/1")

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': redis_url,  # Redis server location and database index
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'buy-sell-pref'  # Prefix for cache keys to avoid collisions
    }
}



CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [redis_url_websocket],
            "capacity": 1000,
            "expiry": 10,
            "max_connections": 5,    # never open more than 5 connections
        },
    },
}

# changed into postgres database for development as well as production

db_host = os.environ.get('POSTGRES_HOST')
db_port = os.environ.get('POSTGRES_PORT')
db_name = os.environ.get('POSTGRES_DB')
db_user = os.environ.get('POSTGRES_USER')
db_pass = os.environ.get('POSTGRES_PASSWORD')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_name,
        'USER': db_user,
        'PASSWORD': db_pass,
        'HOST': db_host,
        'PORT': db_port,
    }
}



# celery configuration

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'



# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'
STATIC_ROOT = Path(__file__).resolve().parents[2] / "staticfiles"

# import cloudinary settings:

from .cloudinary_settings import *

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'rest_framework': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}



REVIEW_RATING_PAGINATION_LIMIT = 2

if os.environ.get('PAGINATION_LIMIT', 2):
    REVIEW_RATING_PAGINATION_LIMIT = int(os.environ.get('PAGINATION_LIMIT', 2))