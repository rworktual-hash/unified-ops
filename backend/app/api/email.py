from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import settings
from app.db.session import get_db
from app.models.email_log_event import EmailLogEvent
from app.models.email_queue_snapshot import EmailQueueSnapshot
from app.models.email_sync_state import EmailSyncState
from app.models.server import Server
from app.schemas.email import (
    EmailLogEventRead,
    EmailOverviewRead,
    EmailQueueSnapshotRead,
    EmailSyncResultRead,
)
from app.services.email_mgmt_sync import STREAM_KEY, compute_email_overview, sync_email_events_from_mgmt_db

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/overview", response_model=EmailOverviewRead)
def email_overview(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
) -> EmailOverviewRead:
    stats = compute_email_overview(db, hours=hours)
    state = db.query(EmailSyncState).filter(EmailSyncState.stream_key == STREAM_KEY).first()
    return EmailOverviewRead(
        **stats,
        sync_configured=bool(settings.email_mgmt_database_url),
        last_source_id=state.last_source_id if state else None,
        last_synced_at=state.last_synced_at if state else None,
        last_sync_error=state.last_error if state else None,
    )


@router.get("/events", response_model=list[EmailLogEventRead])
def list_email_events(
    server_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EmailLogEventRead]:
    q = db.query(EmailLogEvent).order_by(EmailLogEvent.occurred_at.desc())
    if server_id is not None:
        q = q.filter(EmailLogEvent.server_id == server_id)
    rows = q.limit(limit).all()
    return [EmailLogEventRead.model_validate(r) for r in rows]


@router.get("/servers/{server_id}/queue", response_model=EmailQueueSnapshotRead | None, response_model_exclude_none=True)
def latest_email_queue(server_id: int, db: Session = Depends(get_db)) -> EmailQueueSnapshotRead | None:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    row = (
        db.query(EmailQueueSnapshot)
        .filter(EmailQueueSnapshot.server_id == server_id)
        .order_by(EmailQueueSnapshot.collected_at.desc())
        .first()
    )
    if row is None:
        return None
    return EmailQueueSnapshotRead.model_validate(row)


@router.post("/sync", response_model=EmailSyncResultRead)
def sync_email_now(_admin=Depends(require_admin), db: Session = Depends(get_db)) -> EmailSyncResultRead:
    result = sync_email_events_from_mgmt_db(db)
    return EmailSyncResultRead(
        ok=result.get("ok", False),
        inserted=result.get("inserted"),
        skipped=result.get("skipped"),
        reason=result.get("reason"),
        error=result.get("error"),
        last_source_id=result.get("last_source_id"),
    )
