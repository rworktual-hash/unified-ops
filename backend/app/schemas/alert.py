from datetime import datetime

from pydantic import BaseModel


class AlertRead(BaseModel):
    id: int
    server_id: int
    alert_type: str
    severity: str
    status: str
    title: str
    message: str
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class AlertReadWithServer(AlertRead):
    server_name: str
    ip_address: str
    source: str = "collect"


class LiveAlertRead(BaseModel):
    source_id: int
    source: str = "ai_insights"
    alert_type: str
    severity: str
    status: str = "open"
    title: str
    message: str
    ip_address: str = ""
    hostname: str | None = None
    portal_server_name: str | None = None
    first_seen_at: datetime | str | None = None
    last_seen_at: datetime | str | None = None
    inventory_server_id: int | None = None
    inventory_server_name: str | None = None
    inventory_active: bool = False
    matched: bool = False


class LiveAlertsRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    alerts: list[LiveAlertRead]
