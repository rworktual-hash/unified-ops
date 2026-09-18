from celery import Celery
from app.config import settings

celery_app = Celery(
    "unified_ops",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.metrics", "app.tasks.email_sync", "app.tasks.legacy_sync"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

_beat: dict = {}
if settings.metrics_scheduled_collect_enabled:
    _beat["collect-server-metrics"] = {
        "task": "app.tasks.metrics.collect_all_active_servers_task",
        "schedule": settings.metrics_collect_interval_seconds,
        "options": {"expires": max(60.0, settings.metrics_collect_interval_seconds - 30)},
    }
if settings.email_mgmt_scheduled_sync_enabled and settings.email_mgmt_database_url:
    interval = settings.email_mgmt_sync_interval_seconds
    _beat["sync-email-mgmt-logs"] = {
        "task": "app.tasks.email_sync.sync_email_events_task",
        "schedule": interval,
        "options": {"expires": max(30.0, interval - 15)},
    }
if settings.legacy_metrics_scheduled_sync_enabled and settings.legacy_metrics_database_url:
    interval = settings.legacy_metrics_sync_interval_seconds
    _beat["sync-legacy-metrics"] = {
        "task": "app.tasks.legacy_sync.sync_legacy_metrics_task",
        "schedule": interval,
        "options": {"expires": max(60.0, interval - 30)},
    }
celery_app.conf.beat_schedule = _beat
