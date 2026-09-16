"""Read-only pull from email-management DB into nlp-sm (no writes to remote)."""

import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.email_mgmt_sync import sync_email_events_from_mgmt_db

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.email_sync.sync_email_events_task")
def sync_email_events_task() -> dict:
    db = SessionLocal()
    try:
        result = sync_email_events_from_mgmt_db(db)
        if result.get("ok") and result.get("inserted", 0):
            logger.info("Email log sync inserted %s rows", result.get("inserted"))
        elif result.get("skipped"):
            logger.debug("Email log sync skipped: %s", result.get("reason"))
        elif not result.get("ok"):
            logger.warning("Email log sync failed: %s", result.get("error"))
        return result
    finally:
        db.close()
