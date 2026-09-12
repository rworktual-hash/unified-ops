from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.models.server_metric import ServerMetric
from app.monitoring.ssh_test import test_ssh_connection
from app.schemas.connection import ConnectionTestResponse
from app.schemas.metrics import GpuMetricRead, ServerMetricRead, ServerMetricsBundle
from app.schemas.server import ServerCreate, ServerRead, ServerUpdate
from app.services.metrics_collect import collect_and_store_metrics

router = APIRouter(prefix="/servers", tags=["servers"])


@router.post("", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
def create_server(payload: ServerCreate, db: Session = Depends(get_db)) -> Server:
    server = Server(**payload.model_dump())
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


@router.get("", response_model=list[ServerRead])
def list_servers(db: Session = Depends(get_db)) -> list[Server]:
    return db.query(Server).order_by(Server.id).all()


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, db: Session = Depends(get_db)) -> Server:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server


@router.patch("/{server_id}", response_model=ServerRead)
def update_server(server_id: int, payload: ServerUpdate, db: Session = Depends(get_db)) -> Server:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(server, key, value)
    db.commit()
    db.refresh(server)
    return server


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
    result = test_ssh_connection(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
    )
    return ConnectionTestResponse(
        success=result.success,
        message=result.message,
        latency_ms=result.latency_ms,
    )
