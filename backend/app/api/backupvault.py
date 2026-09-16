from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.backupvault_ssh_snapshot import BackupVaultSshSnapshot
from app.models.server import Server
from app.schemas.backupvault import (
    BackupVaultOverviewRead,
    BackupVaultServerOverview,
    BackupVaultSnapshotRead,
)

router = APIRouter(prefix="/backupvault", tags=["backupvault"])


@router.get("/ssh-overview", response_model=BackupVaultOverviewRead)
def backupvault_ssh_overview(db: Session = Depends(get_db)) -> BackupVaultOverviewRead:
    servers = (
        db.query(Server)
        .filter(Server.is_active.is_(True), Server.project == "backupvault")
        .order_by(Server.server_type, Server.server_name)
        .all()
    )
    items: list[BackupVaultServerOverview] = []
    replication_healthy = 0
    replication_unhealthy = 0
    storage_warning = 0
    stale_backup_hosts = 0
    stale_before = datetime.now(timezone.utc) - timedelta(hours=24)

    for server in servers:
        row = (
            db.query(BackupVaultSshSnapshot)
            .filter(BackupVaultSshSnapshot.server_id == server.id)
            .order_by(BackupVaultSshSnapshot.collected_at.desc())
            .first()
        )
        if row:
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
            if row.data_disk_used_pct is not None and row.data_disk_used_pct >= 85:
                storage_warning += 1
            latest = row.latest_backup_at
            if latest:
                if latest.tzinfo is None:
                    latest = latest.replace(tzinfo=timezone.utc)
                if latest < stale_before:
                    stale_backup_hosts += 1
        items.append(
            BackupVaultServerOverview(
                server_id=server.id,
                server_name=server.server_name,
                ip_address=server.ip_address,
                server_type=server.server_type,
                snapshot=BackupVaultSnapshotRead.model_validate(row) if row else None,
            )
        )

    return BackupVaultOverviewRead(
        servers=items,
        total_hosts=len(servers),
        collected_hosts=sum(1 for item in items if item.snapshot is not None),
        replication_healthy=replication_healthy,
        replication_unhealthy=replication_unhealthy,
        storage_warning=storage_warning,
        stale_backup_hosts=stale_backup_hosts,
        note=(
            "Read-only SSH snapshots. Replication requires local socket access; "
            "backup recency checks common /backup, /backups and /var/backups paths."
        ),
    )
