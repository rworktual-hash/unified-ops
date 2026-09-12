from datetime import datetime

from pydantic import BaseModel


class ServerMetricRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    load_1m: float | None
    load_5m: float | None
    load_15m: float | None
    mem_total_mb: int | None
    mem_used_mb: int | None
    mem_used_pct: float | None
    disk_root_used_gb: float | None
    disk_root_total_gb: float | None
    disk_root_pct: float | None
    uptime_seconds: float | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class GpuMetricRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    gpu_index: int
    utilization_pct: float | None
    mem_used_mb: float | None
    mem_total_mb: float | None
    temperature_c: float | None
    status: str
    collect_error: str | None

    model_config = {"from_attributes": True}


class ServerMetricsBundle(BaseModel):
    host: list[ServerMetricRead]
    gpu: list[GpuMetricRead]
