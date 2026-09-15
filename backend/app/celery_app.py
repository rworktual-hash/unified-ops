from celery import Celery
from app.config import settings

celery_app = Celery(
    "unified_ops",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.metrics"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

if settings.metrics_scheduled_collect_enabled:
    celery_app.conf.beat_schedule = {
        "collect-server-metrics": {
            "task": "app.tasks.metrics.collect_all_active_servers_task",
            "schedule": settings.metrics_collect_interval_seconds,
            "options": {"expires": max(60.0, settings.metrics_collect_interval_seconds - 30)},
        },
    }
else:
    celery_app.conf.beat_schedule = {}
