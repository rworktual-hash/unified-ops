"""Read-only pull from legacy portal MySQL (server-management) into nlp-sm."""

import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.legacy_metrics_sync import sync_all_legacy_streams

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.legacy_sync.sync_legacy_metrics_task")
def sync_legacy_metrics_task() -> dict:
    db = SessionLocal()
    try:
        result = sync_all_legacy_streams(db)
        inserted = sum(r.get("inserted", 0) for r in result.get("results", []))
        if result.get("ok") and inserted:
            logger.info("Legacy metrics sync inserted %s points", inserted)
        elif not result.get("ok"):
            logger.warning("Legacy metrics sync had errors: %s", result.get("results"))
        return result
    finally:
        db.close()
