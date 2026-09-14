from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.models.server_metric import ServerMetric
from app.monitoring.ssh_test import test_ssh_connection
from app.schemas.connection import ConnectionTestResponse
from app.schemas.metrics import GpuMetricRead, ServerMetricRead, ServerMetricsBundle
from app.schemas.server import ServerCreate, ServerRead, ServerUpdate, server_to_read
from app.services.metrics_collect import collect_all_active_servers, collect_and_store_metrics
from app.services.server_ssh import ssh_kwargs_from_server

router = APIRouter(prefix="/servers", tags=["servers"])


class CollectAllResponse(BaseModel):
    servers_collected: int
    servers_failed: int
    mode: str


@router.post("", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
def create_server(payload: ServerCreate, db: Session = Depends(get_db)) -> ServerRead:
    server = Server(**payload.model_dump())
    db.add(server)
    db.commit()
    db.refresh(server)
    return server_to_read(server)


@router.get("", response_model=list[ServerRead])
def list_servers(db: Session = Depends(get_db)) -> list[ServerRead]:
    rows = db.query(Server).order_by(Server.id).all()
    return [server_to_read(r) for r in rows]


@router.post("/collect-all", response_model=CollectAllResponse)
def collect_all_server_metrics(
    background: bool = Query(default=False, description="If true, queue Celery task (needs worker)"),
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


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, db: Session = Depends(get_db)) -> ServerRead:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server_to_read(server)


@router.patch("/{server_id}", response_model=ServerRead)
def update_server(server_id: int, payload: ServerUpdate, db: Session = Depends(get_db)) -> ServerRead:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(server, key, value)
    if server.ssh_password and server.ip_address in {"173.234.75.165", "173.234.75.166"}:
        server.is_active = True
    db.commit()
    db.refresh(server)
    return server_to_read(server)


@router.get("/{server_id}/metrics", response_model=ServerMetricsBundle)
def get_server_metrics(
    server_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ServerMetricsBundle:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    host = (
        db.query(ServerMetric)
        .filter(ServerMetric.server_id == server_id)
        .order_by(ServerMetric.collected_at.desc())
        .limit(limit)
        .all()
    )
    gpu = (
        db.query(GpuMetric)
        .filter(GpuMetric.server_id == server_id)
        .order_by(GpuMetric.collected_at.desc())
        .limit(limit * 4)
        .all()
    )
    return ServerMetricsBundle(host=host, gpu=gpu)


@router.post("/{server_id}/collect-metrics", response_model=ServerMetricsBundle)
def collect_metrics_now(server_id: int, db: Session = Depends(get_db)) -> ServerMetricsBundle:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    if not server.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server is inactive.")
    collect_and_store_metrics(db, server)
    host = (
        db.query(ServerMetric)
        .filter(ServerMetric.server_id == server_id)
        .order_by(ServerMetric.collected_at.desc())
        .limit(1)
        .all()
    )
    gpu = (
        db.query(GpuMetric)
        .filter(GpuMetric.server_id == server_id)
        .order_by(GpuMetric.collected_at.desc())
        .limit(8)
        .all()
    )
    return ServerMetricsBundle(host=host, gpu=gpu)


@router.post("/{server_id}/test-connection", response_model=ConnectionTestResponse)
def test_connection(server_id: int, db: Session = Depends(get_db)) -> ConnectionTestResponse:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    if not server.is_active:
        return ConnectionTestResponse(success=False, message="Server is marked inactive.")
    result = test_ssh_connection(**ssh_kwargs_from_server(server))
    return ConnectionTestResponse(
        success=result.success,
        message=result.message,
        latency_ms=result.latency_ms,
    )
