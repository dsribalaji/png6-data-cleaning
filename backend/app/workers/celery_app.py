"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "png6",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
)

# Configuration: jobs safe to run twice (deck)
celery_app.conf.update(
    task_acks_late=True,
    task_track_started=True,
    result_extended=True,
)
