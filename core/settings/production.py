from .base import *


ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")


CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")

# ესენი არის ქროსს საიტ სკრიპტინგისთვის, დაცვისთვის
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# საიტზე შესვლა შეიძლება მოხოლოდ https
SECURE_HSTS_SECONDS = 86400
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True


# -----------------------
# Static Files Configuration
# -----------------------

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


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


# allow Idempotency-Key in headers
from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = list(default_headers) + [
    'Idempotency-Key',
]