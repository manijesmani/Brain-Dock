import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("braindock")

# Every Celery setting lives in Django settings under a `CELERY_` prefix, so
# there is one configuration file rather than two.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
