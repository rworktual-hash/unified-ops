from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LegacyStreamStatusRead(BaseModel):
    domain: str
    enabled: bool
    configured: bool
    database: str | None
    table: str
    metric_cols: list[str]
    row_count: int
    last_source_id: int
    last_synced_at: datetime | None
    last_error: str | None


class LegacyStatusRead(BaseModel):
    configured: bool
    connection_ok: bool
    connection_error: str | None = None
    scheduled_sync_enabled: bool
    streams: list[LegacyStreamStatusRead]


class LegacySyncResultRead(BaseModel):
    ok: bool
    results: list[dict]


class LegacyOverviewRead(BaseModel):
    domain: str
    period_hours: int
    point_count: int
    distinct_hosts: int
    status_counts: dict[str, int]
    averages: dict[str, float]
    latest_by_server: list[dict]


class BackupVaultRunRead(BaseModel):
    id: int
    target_id: int | None
    target_name: str
    db_type: str | None
    target_host: str | None
    backup_type: str | None
    trigger_type: str | None
    status: str | None
    started_at: datetime | None
    completed_at: datetime | None
    file_size_bytes: int | None
    file_size_label: str | None
    file_path: str | None
    error_message: str | None
    duration_seconds: int | None
    destination_count: int
    dest_types: str | None = None


class BackupVaultRunHistoryRead(BaseModel):
    ok: bool
    source: str | None = None
    database: str | None = None
    reason: str | None = None
    total: int = 0
    success_rate: int = 0
    success: int = 0
    failed: int = 0
    partial: int = 0
    running: int = 0
    pending: int = 0
    runs: list[BackupVaultRunRead]


class BackupVaultTargetRead(BaseModel):
    id: int
    name: str
    db_type: str | None
    host: str | None
    port: int | None
    database_name: str | None
    description: str | None
    is_active: bool
    last_status: str | None
    last_started_at: datetime | None


class BackupVaultTargetsRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    targets: list[BackupVaultTargetRead]


class BackupVaultNfsServerRead(BaseModel):
    id: int
    name: str
    host: str | None
    export_path: str | None
    mount_point: str | None
    description: str | None
    role: str | None
    is_active: bool
    status: str | None
    disk_size: str | None
    disk_used: str | None
    disk_avail: str | None


class BackupVaultNfsRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    servers: list[BackupVaultNfsServerRead]


class LegacyMetricPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    source_id: int
    server_id: int | None
    host_key: str | None
    metric_key: str
    metric_value_num: float | None
    metric_value_text: str | None
    recorded_at: datetime
    synced_at: datetime
