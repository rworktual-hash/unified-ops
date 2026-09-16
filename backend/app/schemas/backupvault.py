from datetime import datetime

from pydantic import BaseModel


class BackupVaultSnapshotRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    role: str
    service_active: bool | None
    docker_active: bool | None
    nginx_active: bool | None
    cron_active: bool | None
    containers_running: int | None
    container_summary: str | None
    replication_io_running: bool | None
    replication_sql_running: bool | None
    replica_in_recovery: bool | None
    replication_lag_seconds: int | None
    db_connections: int | None
    slow_queries: int | None
    db_uptime_seconds: int | None
    data_mount: str | None
    data_disk_used_pct: float | None
    data_disk_free_gb: float | None
    latest_backup_at: datetime | None
    latest_backup_path: str | None
    latest_backup_size_bytes: int | None
    backup_process_count: int | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class BackupVaultServerOverview(BaseModel):
    server_id: int
    server_name: str
    ip_address: str
    server_type: str | None
    snapshot: BackupVaultSnapshotRead | None


class BackupVaultOverviewRead(BaseModel):
    read_only: bool = True
    source: str = "ssh"
    servers: list[BackupVaultServerOverview]
    total_hosts: int
    collected_hosts: int
    replication_healthy: int
    replication_unhealthy: int
    storage_warning: int
    stale_backup_hosts: int
    note: str
