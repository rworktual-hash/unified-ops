from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.fleet_collect_run import FleetCollectRun


def record_fleet_collect_run(
    *,
    started_at: datetime,
    servers_ok: int,
    servers_failed: int,
    trigger: str,
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
                trigger=trigger,
                error_summary=error_summary,
            )
        )
        db.commit()
    finally:
        if own:
            db.close()


def latest_fleet_collect_run(db: Session) -> FleetCollectRun | None:
    return db.query(FleetCollectRun).order_by(FleetCollectRun.id.desc()).first()
