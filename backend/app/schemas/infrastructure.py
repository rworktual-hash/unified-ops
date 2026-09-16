from datetime import datetime

from pydantic import BaseModel


class InfrastructureSnapshotRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    role: str
    service_active: bool | None
    nginx_active: bool | None
    kong_active: bool | None
    docker_active: bool | None
    redis_role: str | None
    redis_connected_clients: int | None
    redis_used_memory_bytes: int | None
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
    extra_service_status: str | None
    healthcheck_status: str | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class InfrastructureServerOverview(BaseModel):
    server_id: int
    server_name: str
    ip_address: str
    server_type: str | None
    snapshot: InfrastructureSnapshotRead | None


class InfrastructureOverviewRead(BaseModel):
    read_only: bool = True
    source: str = "ssh"
    servers: list[InfrastructureServerOverview]
    total_hosts: int
    collected_hosts: int
    service_down: int
    storage_warning: int
    replication_healthy: int
    replication_unhealthy: int
    note: str
