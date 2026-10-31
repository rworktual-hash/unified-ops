from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.schemas.process_watch import ProcessWatchCreate, ProcessWatchRead, ProcessWatchUpdate
from app.services.process_watch import (
    ProcessWatchError,
    check_watch,
    create_process_watch,
    delete_process_watch,
    get_process_watch,
    list_process_watches,
    to_read,
    update_process_watch,
)

router = APIRouter(prefix="/process-watches", tags=["process-watches"])


def _watch_or_404(db: Session, watch_id: int):
    row = get_process_watch(db, watch_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watch not found")
    return row


@router.get("", response_model=list[ProcessWatchRead])
def list_watches(db: Session = Depends(get_db)) -> list[ProcessWatchRead]:
    now = datetime.now(timezone.utc)
    return [to_read(row, server_now=now) for row in list_process_watches(db)]


@router.post("", response_model=ProcessWatchRead, status_code=status.HTTP_201_CREATED)
def create_watch(
    payload: ProcessWatchCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> ProcessWatchRead:
    try:
        row = create_process_watch(db, payload, verify_ssh=True)
    except ProcessWatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return to_read(row)


@router.patch("/{watch_id}", response_model=ProcessWatchRead)
def update_watch(
    watch_id: int,
    payload: ProcessWatchUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> ProcessWatchRead:
    try:
        row = update_process_watch(db, _watch_or_404(db, watch_id), payload)
    except ProcessWatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return to_read(row)


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch(
    watch_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> None:
    delete_process_watch(db, _watch_or_404(db, watch_id))


@router.post("/{watch_id}/check", response_model=ProcessWatchRead)
def check_watch_now(
    watch_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> ProcessWatchRead:
    now = datetime.now(timezone.utc)
    row = check_watch(db, _watch_or_404(db, watch_id), now=now, force=force)
    return to_read(row, server_now=now)
