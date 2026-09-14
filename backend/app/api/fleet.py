from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.services.metrics_collect import collect_all_active_servers

router = APIRouter(prefix="/fleet", tags=["fleet"])


class CollectAllResponse(BaseModel):
    servers_collected: int
    servers_failed: int
    mode: str


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
    ok, failed = collect_all_active_servers(db)
    return CollectAllResponse(servers_collected=ok, servers_failed=failed, mode="sync")
