from collections.abc import Iterator

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.services.chat_context import build_ops_context, context_to_prompt_block
from app.services.llm_client import get_chat_llm

SYSTEM_PROMPT = """You are the Worktual Observability assistant.
You help operators with the hosts, metrics, alerts, and inventory in this portal.
Your name is Worktual Observability. Never say Unified Ops.
Answer using ONLY the JSON context provided about connected servers (metrics, alerts, inventory).
If data is missing, say to run "Collect metrics" in the app first.
Do NOT invent server IPs or metrics.
Never instruct the user to run destructive commands (reboot, rm, GPU reset, driver changes).
For fixes that change the system, say they must use Approvals in Worktual Observability.
Be concise, practical, and ops-focused."""

_IDENTITY = (
    "You are the Worktual Observability assistant. "
    "Do not call yourself Unified Ops. "
)


def _split_ready(text: str) -> tuple[str, str]:
    """Hold back a trailing fragment of 'Unified Ops' so a split chunk still rewrites."""
    needle = "unified ops assistant"
    lower = text.lower()
    cut = len(text)
    for size in range(len(needle) - 1, 0, -1):
        if lower.endswith(needle[:size]):
            cut = len(text) - size
            break
    if cut <= 0:
        return "", text
    return present_reply(text[:cut]), text[cut:]


def present_reply(text: str) -> str:
    out = text
    for old, new in (
        ("Unified Ops assistant", "Worktual Observability assistant"),
        ("unified ops assistant", "Worktual Observability assistant"),
        ("Unified Ops", "Worktual Observability"),
        ("unified ops", "Worktual Observability"),
    ):
        out = out.replace(old, new)
    return out


def run_chat(
    db: Session,
    *,
    user_message: str,
    server_id: int | None = None,
) -> tuple[str, list[str]]:
    server_ids = [server_id] if server_id is not None else None
    context = build_ops_context(db, server_ids=server_ids)
    if context["server_count"] == 0:
        return (
            "No active connected servers in scope. Enable DR GPU hosts (148/149) or pick a valid server.",
            [],
        )

    names = [s["name"] for s in context["connected_servers"]]
    context_block = context_to_prompt_block(context)
    llm = get_chat_llm()
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"{_IDENTITY}\n\n"
                    f"Context JSON:\n{context_block}\n\n"
                    f"User question:\n{user_message.strip()}"
                )
            ),
        ]
    )
    reply = response.content if isinstance(response.content, str) else str(response.content)
    return present_reply(reply).strip(), names


def _chunk_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return ""


def stream_chat(
    db: Session,
    *,
    user_message: str,
    server_id: int | None = None,
) -> Iterator[str]:
    server_ids = [server_id] if server_id is not None else None
    context = build_ops_context(db, server_ids=server_ids)
    if context["server_count"] == 0:
        yield (
            "No active connected servers in scope. Enable DR GPU hosts (148/149) or pick a valid server."
        )
        return

    context_block = context_to_prompt_block(context)
    llm = get_chat_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"{_IDENTITY}\n\n"
                f"Context JSON:\n{context_block}\n\n"
                f"User question:\n{user_message.strip()}"
            )
        ),
    ]
    hold = ""
    for chunk in llm.stream(messages):
        text = _chunk_text(getattr(chunk, "content", ""))
        if not text:
            continue
        hold += text
        ready, hold = _split_ready(hold)
        if ready:
            yield ready
    if hold:
        yield present_reply(hold)
