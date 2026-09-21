from datetime import datetime

from pydantic import BaseModel, computed_field


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
    power_w: float | None
    clock_mhz: float | None
    status: str
    collect_error: str | None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mem_used_pct(self) -> float | None:
        if self.mem_used_mb is None or self.mem_total_mb is None or self.mem_total_mb <= 0:
            return None
        return self.mem_used_mb / self.mem_total_mb * 100.0


class GpuProductSnapshotRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    compute_process_count: int | None
    compute_mem_used_mb: float | None
    compute_process_names: str | None
    docker_containers_running: int | None
    docker_active: bool | None = None
    docker_container_status: str | None = None
    process_sample: str | None = None
    log_tail: str | None = None
    gpu_model_name: str | None
    driver_version: str | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class GpuInsightsSnapshotRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    process_count: int | None
    tcp_inuse: int | None
    tcp_connection_lines: int | None
    tcp_established: int | None
    listen_sockets: int | None
    listen_port_8000: int | None
    listen_port_8011: int | None = None
    localhost_ping_ok: bool | None = None
    cpu_util_pct: float | None
    gpu_util_avg: float | None
    gpu_temp_avg: float | None
    net_rx_bytes: int | None
    net_tx_bytes: int | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class ServerMetricsBundle(BaseModel):
    host: list[ServerMetricRead]
    gpu: list[GpuMetricRead]
    gpu_latest: list[GpuMetricRead] = []
    gpu_product: GpuProductSnapshotRead | None = None
    gpu_insights: GpuInsightsSnapshotRead | None = None


class ServerMetricsHistoryResponse(BaseModel):
    server_id: int
    hours: float
    host: list[ServerMetricRead]
    gpu: list[GpuMetricRead]
    gpu_insights: list[GpuInsightsSnapshotRead]
