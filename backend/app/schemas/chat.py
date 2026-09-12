from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    server_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    servers_in_context: list[str]
