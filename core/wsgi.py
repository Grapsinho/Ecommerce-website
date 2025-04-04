import os
from django.core.wsgi import get_wsgi_application
from core.settings.base import DEBUG  # Import DEBUG from the base settings

# Use DEBUG to set the appropriate settings module for WSGI
if DEBUG == "True":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')

application = get_wsgi_application()