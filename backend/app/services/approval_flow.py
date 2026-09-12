import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.executors.controlled import ExecutionResult, execute_approved_action
from app.models.agent_action import AgentAction
from app.models.approval_request import ApprovalRequest
from app.models.server import Server
from app.policies.executor_actions import is_action_allowed


def create_approval_request(
    db: Session,
    *,
    server_id: int,
    action_key: str,
    action_params: dict | None,
    alert_id: int | None,
    request_notes: str | None,
    requested_by: str,
) -> ApprovalRequest:
    server = db.get(Server, server_id)
    if server is None:
        raise ValueError("Server not found")
    if not server.is_active:
        raise ValueError("Server is inactive")

    allowed, reason = is_action_allowed(action_key, action_params)
    if not allowed:
        raise ValueError(reason)

    now = datetime.now(timezone.utc)
    row = ApprovalRequest(
        server_id=server_id,
        alert_id=alert_id,
        action_key=action_key,
        action_params=json.dumps(action_params) if action_params else None,
        status="pending",
        request_notes=request_notes,
        requested_by=requested_by,
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _log_execution(
    db: Session,
    *,
    server_id: int,
    alert_id: int | None,
    summary: str,
    diagnosis: str,
) -> None:
    db.add(
        AgentAction(
            server_id=server_id,
            alert_id=alert_id,
            action_type="execute",
            status="completed",
            summary=summary,
            diagnosis=diagnosis,
            recommendation="executed_after_approval",
            tool_trace=None,
            created_at=datetime.now(timezone.utc),
        )
    )


def approve_request(db: Session, approval_id: int, *, decided_by: str) -> ApprovalRequest:
    row = db.get(ApprovalRequest, approval_id)
    if row is None:
        raise ValueError("Approval request not found")
    if row.status != "pending":
        raise ValueError(f"Request is not pending (status={row.status}).")

    server = db.get(Server, row.server_id)
    if server is None:
        raise ValueError("Server not found")

    now = datetime.now(timezone.utc)
    row.status = "approved"
    row.decided_by = decided_by
    row.decided_at = now

    result: ExecutionResult = execute_approved_action(db, server, row.action_key, row.action_params)
    row.executed_at = now
    row.execution_result = json.dumps(
        {"success": result.success, "message": result.message, "detail": result.detail}
    )
    row.status = "executed" if result.success else "failed"
    _log_execution(
        db,
        server_id=row.server_id,
        alert_id=row.alert_id,
        summary=result.message,
        diagnosis=row.execution_result or "",
    )
    db.commit()
    db.refresh(row)
    return row


def reject_request(db: Session, approval_id: int, *, decided_by: str) -> ApprovalRequest:
    row = db.get(ApprovalRequest, approval_id)
    if row is None:
        raise ValueError("Approval request not found")
    if row.status != "pending":
        raise ValueError(f"Request is not pending (status={row.status}).")
    now = datetime.now(timezone.utc)
    row.status = "rejected"
    row.decided_by = decided_by
    row.decided_at = now
    db.commit()
    db.refresh(row)
    return row
