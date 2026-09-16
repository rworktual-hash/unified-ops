import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.fleet_collect_run import FleetCollectRun

logger = logging.getLogger(__name__)


def record_fleet_collect_run(
    *,
    started_at: datetime,
    servers_ok: int,
    servers_failed: int,
    run_trigger: str,
    error_summary: str | None = None,
    db: Session | None = None,
) -> None:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        db.add(
            FleetCollectRun(
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                servers_ok=servers_ok,
                servers_failed=servers_failed,
                run_trigger=run_trigger,
                error_summary=error_summary,
            )
        )
        db.commit()
        logger.info(
            "Fleet collect run logged: ok=%s failed=%s trigger=%s",
            servers_ok,
            servers_failed,
            run_trigger,
        )
    except Exception:
        logger.exception("Failed to write fleet_collect_runs row")
        if not own:
            db.rollback()
    finally:
        if own:
            db.close()


def latest_fleet_collect_run(db: Session) -> FleetCollectRun | None:
    return db.query(FleetCollectRun).order_by(FleetCollectRun.id.desc()).first()
