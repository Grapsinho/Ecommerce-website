from .base import *

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

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


# email sending configuration
email_backend = os.environ.get('DEVELOPMENT_EMAIL_BACKEND')
email_host = os.environ.get('DEVELOPMENT_EMAIL_HOST')
email_use_tls = os.environ.get('DEVELOPMENT_EMAIL_USE_TLS')
email_port = os.environ.get('DEVELOPMENT_EMAIL_PORT')
email_host_user = os.environ.get('DEVELOPMENT_EMAIL_HOST_USER')
email_host_password = os.environ.get('DEVELOPMENT_EMAIL_HOST_PASSWORD')

EMAIL_BACKEND = email_backend
EMAIL_HOST = email_host
EMAIL_USE_TLS = email_use_tls
EMAIL_PORT = email_port
EMAIL_HOST_USER = email_host_user
EMAIL_HOST_PASSWORD = email_host_password


# For django debug toolbar

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]