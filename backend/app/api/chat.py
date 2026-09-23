import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import run_chat, stream_chat

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        reply, names = run_chat(db, user_message=payload.message, server_id=payload.server_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed: {exc}",
        ) from exc
    return ChatResponse(reply=reply, servers_in_context=names)


@router.post("/stream")
def chat_stream(payload: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    def generate():
        try:
            for piece in stream_chat(db, user_message=payload.message, server_id=payload.server_id):
                yield _sse({"t": piece})
            yield _sse({"done": True})
        except Exception as exc:
            yield _sse({"error": f"LLM request failed: {str(exc)[:300]}"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
