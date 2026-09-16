from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.infrastructure_ssh_snapshot import InfrastructureSshSnapshot
from app.models.server import Server
from app.schemas.infrastructure import (
    InfrastructureOverviewRead,
    InfrastructureServerOverview,
    InfrastructureSnapshotRead,
)

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])


@router.get("/ssh-overview", response_model=InfrastructureOverviewRead)
def infrastructure_ssh_overview(db: Session = Depends(get_db)) -> InfrastructureOverviewRead:
    servers = (
        db.query(Server)
        .filter(
            Server.is_active.is_(True),
            Server.project.in_(("infrastructure", "infra")),
        )
        .order_by(Server.server_type, Server.server_name)
        .all()
    )
    items: list[InfrastructureServerOverview] = []
    service_down = 0
    storage_warning = 0
    replication_healthy = 0
    replication_unhealthy = 0

    for server in servers:
        row = (
            db.query(InfrastructureSshSnapshot)
            .filter(InfrastructureSshSnapshot.server_id == server.id)
            .order_by(InfrastructureSshSnapshot.collected_at.desc())
            .first()
        )
        if row:
            if row.service_active is False:
                service_down += 1
            if row.data_disk_used_pct is not None and row.data_disk_used_pct >= 85:
                storage_warning += 1
            if row.role == "mysql":
                states = (row.replication_io_running, row.replication_sql_running)
                if all(value is True for value in states):
                    replication_healthy += 1
                elif any(value is not None for value in states):
                    replication_unhealthy += 1
            elif row.role == "postgres" and row.replica_in_recovery is not None:
                if row.replica_in_recovery and (
                    row.replication_lag_seconds is None
                    or row.replication_lag_seconds <= 300
                ):
                    replication_healthy += 1
                else:
                    replication_unhealthy += 1
        items.append(
            InfrastructureServerOverview(
                server_id=server.id,
                server_name=server.server_name,
                ip_address=server.ip_address,
                server_type=server.server_type,
                snapshot=InfrastructureSnapshotRead.model_validate(row) if row else None,
            )
        )

    return InfrastructureOverviewRead(
        servers=items,
        total_hosts=len(servers),
        collected_hosts=sum(1 for item in items if item.snapshot is not None),
        service_down=service_down,
        storage_warning=storage_warning,
        replication_healthy=replication_healthy,
        replication_unhealthy=replication_unhealthy,
        note=(
            "Read-only SSH snapshots for nginx, Kong, databases, Redis, Grafana, PBX/SIP, and "
            "platform hosts. Optional INFRASTRUCTURE_APP_SERVICE_UNITS and "
            "INFRASTRUCTURE_LOCAL_HEALTH_URLS extend probes safely."
        ),
    )
