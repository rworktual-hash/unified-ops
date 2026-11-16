from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


RunType = Literal["agent", "llm", "tool", "skill", "chain"]
ToolSource = Literal["builtin", "mcp"]
AgentMode = Literal["agent", "team", "orchestrator", "workflow"]
RunStatus = Literal["success", "error"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=128)


class ProjectPublic(BaseModel):
    id: int
    name: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyPublic(BaseModel):
    id: int
    project_id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked: bool


class ApiKeyCreated(ApiKeyPublic):
    api_key: str


class ApiKeyCreate(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=128)


class IngestRun(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    parent_id: str | None = Field(default=None, max_length=64)
    type: RunType
    name: str = Field(min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    system_prompt: str | None = None
    input: Any = None
    output: Any = None
    status: RunStatus = "success"
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    instructions: str | None = None
    tool_source: ToolSource | None = None
    connector: str | None = Field(default=None, max_length=128)


class IngestTrace(BaseModel):
    id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    session_id: str | None = Field(default=None, max_length=200)
    customer: str | None = Field(default=None, max_length=128)
    customer_role: str | None = Field(default=None, max_length=32)
    agent: str | None = Field(default=None, max_length=128)
    agent_mode: AgentMode | None = None
    status: RunStatus | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class IngestBody(BaseModel):
    trace: IngestTrace
    runs: list[IngestRun] = Field(min_length=1, max_length=100)


class IngestResult(BaseModel):
    trace_id: int
    external_id: str
    project: str
    status: str
    run_count: int


class RunPublic(BaseModel):
    id: int
    external_id: str
    parent_id: str | None
    type: str
    name: str
    model: str | None
    system_prompt: str | None
    input: str | None
    output: str | None
    status: str
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    total_cost: float | None = None
    tool_source: str = ""
    connector: str = ""


class TraceListItem(BaseModel):
    id: int | str
    project_id: int
    project: str
    name: str
    status: str
    error: str | None
    started_at: datetime
    finished_at: datetime | None
    latency_ms: int | None
    agents: list[str]
    tools: list[str]
    failed_tools: list[str]
    models: list[str]
    total_tokens: int
    run_count: int
    session_id: str | None = None
    total_cost: float | None = None
    customer: str = ""
    customer_role: str = ""
    agent_name: str = ""
    agent_mode: str = ""
    skills: list[str] = Field(default_factory=list)


class TraceDetail(TraceListItem):
    runs: list[RunPublic]


class SummaryPublic(BaseModel):
    total: int
    success: int
    error: int
    avg_latency_ms: int | None
    total_tokens: int
    total_cost: float | None = None
    models: list[str]
    customers: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
