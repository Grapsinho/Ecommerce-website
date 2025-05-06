import os
from celery import Celery
from core.settings.base import DEBUG

import logging

logger = logging.getLogger("rest_framework")

if DEBUG:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')

app = Celery('core')

# Pull configuration from Django settings via CELERY_... keys
app.config_from_object('django.conf:settings', namespace='CELERY')

# silence the warnings
app.conf.broker_connection_retry_on_startup = True

# Auto-discover tasks.py in each application registered in INSTALLED_APPS
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    logger.info(f'Request: {self.request!r}')