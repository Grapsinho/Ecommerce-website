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

app.conf.broker_pool_limit = 1               # only one connection in the pool
app.conf.broker_connection_retry_on_startup = True
app.conf.worker_send_task_events = False     # don’t send/receive task‑event heartbeat chatter
app.conf.task_send_sent_event = False

# Auto-discover tasks.py in each application registered in INSTALLED_APPS
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    logger.info(f'Request: {self.request!r}')