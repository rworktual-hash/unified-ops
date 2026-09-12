import json
from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalCreate(BaseModel):
    server_id: int
    action_key: str = Field(..., min_length=1, max_length=64)
    action_params: dict | None = None
    alert_id: int | None = None
    request_notes: str | None = Field(default=None, max_length=2000)
    requested_by: str = Field(default="operator", max_length=128)


class ApprovalRead(BaseModel):
    id: int
    server_id: int
    alert_id: int | None
    action_key: str
    action_params: str | None
    status: str
    request_notes: str | None
    requested_by: str
    decided_by: str | None
    execution_result: str | None
    created_at: datetime
    decided_at: datetime | None
    executed_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalReadWithServer(ApprovalRead):
    server_name: str
    ip_address: str


class ApprovalDecision(BaseModel):
    decided_by: str = Field(default="operator", max_length=128)
