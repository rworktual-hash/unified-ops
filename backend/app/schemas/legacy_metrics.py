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
