import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.process_watch import check_enabled_watches

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.process_watch.check_process_watches_task")
def check_process_watches_task() -> dict[str, int]:
    db = SessionLocal()
    try:
        return check_enabled_watches(db)
    except Exception:
        logger.exception("Process watch check failed")
        raise
    finally:
        db.close()
