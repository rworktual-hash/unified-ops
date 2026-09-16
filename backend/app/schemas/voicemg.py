from datetime import datetime

from pydantic import BaseModel


class VoiceMgSnapshotRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    role: str
    service_active: bool | None
    docker_active: bool | None
    nginx_active: bool | None
    containers_running: int | None
    container_summary: str | None
    app_process_count: int | None
    app_process_sample: str | None
    gpu_device_count: int | None
    gpu_util_summary: str | None
    data_mount: str | None
    data_disk_used_pct: float | None
    data_disk_free_gb: float | None
    extra_service_status: str | None
    healthcheck_status: str | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class VoiceMgServerOverview(BaseModel):
    server_id: int
    server_name: str
    ip_address: str
    server_type: str | None
    snapshot: VoiceMgSnapshotRead | None


class VoiceMgOverviewRead(BaseModel):
    read_only: bool = True
    source: str = "ssh"
    servers: list[VoiceMgServerOverview]
    total_hosts: int
    collected_hosts: int
    vmg_hosts: int
    stt_hosts: int
    service_down: int
    storage_warning: int
    note: str
