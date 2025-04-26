import os
from celery import Celery
from core.settings.base import DEBUG

if DEBUG:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')

app = Celery('core')

# Pull configuration from Django settings via CELERY_... keys
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in each application registered in INSTALLED_APPS
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')