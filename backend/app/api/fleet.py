from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import settings
from app.db.session import get_db
from app.services.fleet_collect_log import latest_fleet_collect_run, record_fleet_collect_run
from app.services.metrics_collect import collect_all_active_servers

router = APIRouter(prefix="/fleet", tags=["fleet"])


class CollectAllResponse(BaseModel):
    servers_collected: int
    servers_failed: int
    mode: str


class FleetCollectStatusResponse(BaseModel):
    scheduled_collect_enabled: bool
    interval_seconds: float
    last_run_at: datetime | None
    last_servers_ok: int | None
    last_servers_failed: int | None
    last_trigger: str | None


@router.get("/collect-status", response_model=FleetCollectStatusResponse)
def fleet_collect_status(db: Session = Depends(get_db)) -> FleetCollectStatusResponse:
    last = latest_fleet_collect_run(db)
    return FleetCollectStatusResponse(
        scheduled_collect_enabled=settings.metrics_scheduled_collect_enabled,
        interval_seconds=settings.metrics_collect_interval_seconds,
        last_run_at=last.finished_at if last else None,
        last_servers_ok=last.servers_ok if last else None,
        last_servers_failed=last.servers_failed if last else None,
        last_trigger=last.run_trigger if last else None,
    )


@router.post("/collect-metrics", response_model=CollectAllResponse)
def fleet_collect_metrics(
    background: bool = Query(default=False),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> CollectAllResponse:
    if background:
        try:
            from app.tasks.metrics import collect_all_active_servers_task

            collect_all_active_servers_task.delay()
            return CollectAllResponse(servers_collected=0, servers_failed=0, mode="celery_queued")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Celery unavailable: {exc}. Use background=false or start worker.",
            ) from exc
    started = datetime.now(timezone.utc)
    ok, failed = collect_all_active_servers(db)
    record_fleet_collect_run(
        started_at=started,
        servers_ok=ok,
        servers_failed=failed,
        run_trigger="api_sync",
        db=db,
    )
    return CollectAllResponse(servers_collected=ok, servers_failed=failed, mode="sync")
