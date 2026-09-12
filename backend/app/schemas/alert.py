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
