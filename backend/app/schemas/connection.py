from pydantic import BaseModel


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None
