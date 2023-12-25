import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_keenthemes.settings')
# app = Celery('django_shop_m89_final')
app = Celery('_keenthemes')
app.config_from_object('django.conf.settings', namespace='CELERY')
app.autodiscover_tasks()
