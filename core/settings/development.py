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
    "http://127.0.0.1:5501",
]


# For django debug toolbar

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]

# email sending configuration
email_backend = os.environ.get('EMAIL_BACKEND')
email_host = os.environ.get('EMAIL_HOST')
email_use_tls = os.environ.get('EMAIL_USE_TLS')
email_port = os.environ.get('EMAIL_PORT')
email_host_user = os.environ.get('EMAIL_HOST_USER')
email_host_password = os.environ.get('EMAIL_HOST_PASSWORD')

EMAIL_BACKEND = email_backend
EMAIL_HOST = email_host
EMAIL_USE_TLS = email_use_tls
EMAIL_PORT = email_port
EMAIL_HOST_USER = email_host_user
EMAIL_HOST_PASSWORD = email_host_password