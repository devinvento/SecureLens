import os
from celery import Celery
from app.core.config import settings

celery_app = Celery("app")
celery_app.conf.broker_url = settings.REDIS_URL
celery_app.conf.result_backend = settings.REDIS_URL
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.autodiscover_tasks(["app"])
