from datetime import datetime

from pydantic import BaseModel


class AgentActionRead(BaseModel):
    id: int
    server_id: int
    alert_id: int | None
    action_type: str
    status: str
    summary: str
    diagnosis: str
    recommendation: str
    tool_trace: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestigationResponse(BaseModel):
    agent_action_id: int
    summary: str
    diagnosis: str
    recommendation: str
