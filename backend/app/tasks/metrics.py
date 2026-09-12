from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.metrics_collect import collect_all_active_servers


@celery_app.task(name="app.tasks.metrics.collect_all_active_servers_task")
def collect_all_active_servers_task() -> dict[str, int]:
    db = SessionLocal()
    try:
        count = collect_all_active_servers(db)
    finally:
        db.close()
    return {"servers_collected": count}
