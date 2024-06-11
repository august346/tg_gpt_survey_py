import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

from . import tasks

BROKER_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
# BACKEND_URL = os.environ.get("DB_URL", "db+postgresql://survey:example@pgbouncer/survey")
BACKEND_URL = os.environ.get("DB_URL", "postgresql://survey:example@pgbouncer/survey")

app = Celery('survey',
             broker=BROKER_URL,
             backend=BACKEND_URL)

app.conf.update(
    result_expires=3600,
    beat_schedule={
        'scrape-vacancies-everyday': {
            'task': 'tasks.scrape_vacancies',
            'schedule': crontab(hour="0", minute="0")
        },
    },
)

app.autodiscover_tasks()


@worker_ready.connect
def on_worker_ready(sender=None, **kwargs):
    tasks.scrape_vacancies.delay()
