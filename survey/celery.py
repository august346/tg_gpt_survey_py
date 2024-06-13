import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready


BROKER_URL = os.environ.get("BROKER_URL", "redis://redis:6379/0")
BACKEND_URL = os.environ.get("BACKEND_URL", "db+postgresql://survey:example@pgbouncer/survey")

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
    from . import tasks

    tasks.scrape_vacancies.delay()
