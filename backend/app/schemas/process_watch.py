from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProcessWatchCreate(BaseModel):
    ip_address: str = Field(min_length=3, max_length=45)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(default="root", min_length=1, max_length=128)
    ssh_password: str = Field(min_length=1, max_length=512)
    label: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    process_name: str = Field(min_length=1, max_length=128)
    listen_port: int = Field(default=0, ge=0, le=65535)
    recipients: list[str] = Field(default_factory=list, max_length=20)
    check_interval: int = Field(ge=1, le=86400)
    check_interval_unit: Literal["seconds", "minutes"] = "seconds"
    mail_interval_minutes: int = Field(ge=1, le=10080)
    enabled: bool = True


class ProcessWatchUpdate(BaseModel):
    ip_address: str = Field(min_length=3, max_length=45)
    ssh_port: int = Field(ge=1, le=65535)
    ssh_username: str = Field(min_length=1, max_length=128)
    ssh_password: str = Field(default="", max_length=512)
    label: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    process_name: str = Field(min_length=1, max_length=128)
    listen_port: int = Field(default=0, ge=0, le=65535)
    recipients: list[str] = Field(default_factory=list, max_length=20)
    check_interval: int = Field(ge=1, le=86400)
    check_interval_unit: Literal["seconds", "minutes"] = "seconds"
    mail_interval_minutes: int = Field(ge=1, le=10080)
    enabled: bool = True


class ProcessMailEntry(BaseModel):
    email: str
    team: str = ""


class ProcessMailDefaults(BaseModel):
    recipients: list[str] = Field(default_factory=list, max_length=20)
    entries: list[ProcessMailEntry] = Field(default_factory=list, max_length=20)


class ProcessWatchMailRead(BaseModel):
    id: int
    watch_id: int | None
    label: str
    ip_address: str
    process_name: str
    kind: Literal["down", "up"]
    mailed_at: datetime

    model_config = {"from_attributes": True}


class ProcessWatchChangeRead(BaseModel):
    id: int
    watch_id: int | None
    label: str
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProcessWatchRead(BaseModel):
    id: int
    ip_address: str
    ssh_port: int
    ssh_username: str
    label: str
    description: str
    process_name: str
    pid: str
    service_port: str
    listen_port: int = 0
    recipients: list[str]
    check_interval: int
    check_interval_unit: str
    mail_interval_minutes: int
    enabled: bool
    status: str
    last_checked_at: datetime | None
    down_since: datetime | None
    resolved_at: datetime | None
    last_emailed_at: datetime | None
    mail_sent: bool | None
    mail_error: str | None
    last_error: str | None
    created_at: datetime
    server_now: datetime

    model_config = {"from_attributes": True}
