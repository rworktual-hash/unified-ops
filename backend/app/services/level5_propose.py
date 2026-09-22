"""Level 5: propose one allowlisted command after Investigate. Never auto-execute."""

from __future__ import annotations

import json

from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.policies.executor_actions import GPU_RESTART_SERVICES, is_gpu_host

if TYPE_CHECKING:
    from app.models.approval_request import ApprovalRequest
    from app.models.server import Server

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

GPU_FIX_COMMANDS: dict[str, dict[str, str]] = {
    "systemctl_restart": {
        "label": "Restart Docker",
        "command": "sudo systemctl restart docker",
        "impact": (
            "GPU host only. Restarts the Docker service. Containers bounce. "
            "Does not reboot the host, reset GPUs, change NVIDIA/CUDA, or write MariaDB .222."
        ),
    },
}

COMMAND_SPECS = {**SAFE_COMMANDS, **GPU_FIX_COMMANDS}


def _docker_down(extras: dict[str, Any] | None) -> bool:
    if not extras:
        return False
    return extras.get("docker_active") is False


def pick_proposal(
    alert_type: str | None,
    host_collect_error: str | None,
    *,
    server: "Server | None" = None,
    extras: dict[str, Any] | None = None,
) -> tuple[str, dict[str, str]]:
    if (alert_type or "") == "collect_failed" or host_collect_error:
        return "ssh_verify", {}
    if is_gpu_host(server) and getattr(server, "is_active", False) and _docker_down(extras):
        return "systemctl_restart", {"service_name": "docker"}
    return "recollect_metrics", {}


def pick_action_key(alert_type: str | None, host_collect_error: str | None) -> str:
    action_key, _params = pick_proposal(alert_type, host_collect_error)
    return action_key


def build_guardrail_params(
    *,
    server: "Server",
    action_key: str,
    alert_type: str | None,
    alert_message: str | None,
    diagnosis: str | None,
    extra_params: dict[str, str] | None = None,
) -> dict[str, str]:
    spec = COMMAND_SPECS[action_key]
    command = spec["command"]
    impact = spec["impact"]
    if action_key == "systemctl_restart":
        service = (extra_params or {}).get("service_name") or "docker"
        if service not in GPU_RESTART_SERVICES:
            service = "docker"
        command = f"sudo systemctl restart {service}"
    parts: list[str] = []
    if alert_message and alert_message.strip():
        parts.append(alert_message.strip())
    if diagnosis:
        first = next((line.strip() for line in diagnosis.splitlines() if line.strip()), "")
        if first and first not in parts:
            parts.append(first[:300])
    reason = " — ".join(parts) or "Operator requested a Level 5 check."
    params: dict[str, str] = {
        "alert_type": (alert_type or "manual").strip()[:64],
        "alert_reason": (reason or "Operator requested a Level 5 check.")[:800],
        "proposed_command": command,
        "impact": impact,
        "host": f"{server.server_name} ({server.ip_address}:{server.ssh_port})",
    }
    if extra_params:
        params.update(extra_params)
    return params


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
    extras: dict[str, Any] | None = None,
) -> "ApprovalRequest":
    from app.models.approval_request import ApprovalRequest

    action_key, extra = pick_proposal(
        alert_type, host_collect_error, server=server, extras=extras
    )
    params = build_guardrail_params(
        server=server,
        action_key=action_key,
        alert_type=alert_type,
        alert_message=alert_message,
        diagnosis=diagnosis,
        extra_params=extra,
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
    spec = COMMAND_SPECS[action_key]
    notes = (
        f"Alert: {params['alert_type']}. Reason: {params['alert_reason']}. "
        f"Proposed: {spec['label']}. Command: {params['proposed_command']}."
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
