"""Level 5: propose one allowlisted command after Investigate. Never auto-execute."""

from __future__ import annotations

import json

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.approval_request import ApprovalRequest
    from app.models.server import Server

# Human-readable text for the two actions the executor may run today.
SAFE_COMMANDS: dict[str, dict[str, str]] = {
    "recollect_metrics": {
        "label": "Recollect metrics",
        "command": (
            "SSH to the inventory host and collect CPU load, RAM, disk, and GPU "
            "(util / memory / temp / status). Store the snapshot and re-evaluate alerts."
        ),
        "impact": "Read-only collect. Does not restart, stop, kill, delete, or change config.",
    },
    "ssh_verify": {
        "label": "SSH verify",
        "command": "Open an SSH session and run the connection test command only.",
        "impact": "Checks login only. Does not change the server.",
    },
}


def pick_action_key(alert_type: str | None, host_collect_error: str | None) -> str:
    if (alert_type or "") == "collect_failed" or host_collect_error:
        return "ssh_verify"
    return "recollect_metrics"


def build_guardrail_params(
    *,
    server: "Server",
    action_key: str,
    alert_type: str | None,
    alert_message: str | None,
    diagnosis: str | None,
) -> dict[str, str]:
    spec = SAFE_COMMANDS[action_key]
    parts: list[str] = []
    if alert_message and alert_message.strip():
        parts.append(alert_message.strip())
    if diagnosis:
        first = diagnosis.splitlines()[0].strip()
        if first and first not in parts:
            parts.append(first[:300])
    reason = " — ".join(parts) or "Operator requested a Level 5 check."
    return {
        "alert_type": (alert_type or "manual").strip()[:64],
        "alert_reason": (reason or "Operator requested a Level 5 check.")[:800],
        "proposed_command": spec["command"],
        "impact": spec["impact"],
        "host": f"{server.server_name} ({server.ip_address}:{server.ssh_port})",
    }


def parse_guardrail(action_params: str | None) -> dict[str, str | None]:
    empty = {
        "alert_type": None,
        "alert_reason": None,
        "proposed_command": None,
        "impact": None,
        "host": None,
    }
    if not action_params:
        return empty
    try:
        raw = json.loads(action_params)
    except json.JSONDecodeError:
        return empty
    if not isinstance(raw, dict):
        return empty
    out = dict(empty)
    for key in empty:
        val = raw.get(key)
        out[key] = str(val)[:800] if val is not None else None
    return out


def propose_after_investigation(
    db: Session,
    *,
    server: "Server",
    alert_id: int | None,
    alert_type: str | None,
    alert_message: str | None,
    diagnosis: str | None,
    host_collect_error: str | None,
) -> "ApprovalRequest":
    from app.models.approval_request import ApprovalRequest
    action_key = pick_action_key(alert_type, host_collect_error)
    params = build_guardrail_params(
        server=server,
        action_key=action_key,
        alert_type=alert_type,
        alert_message=alert_message,
        diagnosis=diagnosis,
    )
    existing = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.server_id == server.id,
            ApprovalRequest.action_key == action_key,
            ApprovalRequest.status == "pending",
        )
        .order_by(ApprovalRequest.created_at.desc())
        .first()
    )
    notes = (
        f"Alert: {params['alert_type']}. Reason: {params['alert_reason']}. "
        f"Proposed: {SAFE_COMMANDS[action_key]['label']}."
    )[:2000]
    if existing:
        existing.alert_id = alert_id or existing.alert_id
        existing.action_params = json.dumps(params)
        existing.request_notes = notes
        db.commit()
        db.refresh(existing)
        return existing
    from app.services.approval_flow import create_approval_request

    return create_approval_request(
        db,
        server_id=server.id,
        action_key=action_key,
        action_params=params,
        alert_id=alert_id,
        request_notes=notes,
        requested_by="agent",
    )
