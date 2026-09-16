import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.fleet_collect_log import record_fleet_collect_run
from app.services.metrics_collect import collect_all_active_servers

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.metrics.collect_all_active_servers_task")
def collect_all_active_servers_task() -> dict[str, int]:
    started = datetime.now(timezone.utc)
    db = SessionLocal()
    ok = 0
    failed = 0
    err: str | None = None
    try:
        ok, failed = collect_all_active_servers(db)
    except Exception as exc:
        err = str(exc)[:2000]
        logger.exception("Fleet collect task failed")
    finally:
        db.close()
    record_fleet_collect_run(
        started_at=started,
        servers_ok=ok,
        servers_failed=failed,
        run_trigger="celery",
        error_summary=err,
    )
    if err:
        raise RuntimeError(err)
    return {"servers_collected": ok, "servers_failed": failed}
