from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.services.chat_context import build_ops_context, context_to_prompt_block
from app.services.llm_client import get_chat_llm

SYSTEM_PROMPT = """You are Unified Ops assistant for Worktual GPU infrastructure.
Answer using ONLY the JSON context provided about connected servers (metrics, alerts, inventory).
If data is missing, say to run "Collect metrics" in the app first.
Do NOT invent server IPs or metrics.
Never instruct the user to run destructive commands (reboot, rm, GPU reset, driver changes).
For fixes that change the system, say they must use Approvals in Unified Ops.
Be concise, practical, and ops-focused."""


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
                    f"Context JSON:\n{context_block}\n\n"
                    f"User question:\n{user_message.strip()}"
                )
            ),
        ]
    )
    reply = response.content if isinstance(response.content, str) else str(response.content)
    return reply.strip(), names
