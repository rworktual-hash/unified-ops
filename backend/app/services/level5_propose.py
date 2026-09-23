"""Level 5: propose one allowlisted command after Investigate. Never auto-execute."""

from __future__ import annotations

import json

from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.policies.executor_actions import EXACT_RESTART_COMMANDS, recovery_unit

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

RESTART_SPECS: dict[str, dict[str, str]] = {
    "docker": {
        "label": "Restart Docker",
        "command": EXACT_RESTART_COMMANDS["docker"],
        "impact": (
            "Restarts Docker on this host only. Containers bounce. "
            "Does not reboot the host, reset GPUs, delete mail, restore backups, or write MariaDB .222."
        ),
    },
    "postfix": {
        "label": "Restart Postfix",
        "command": EXACT_RESTART_COMMANDS["postfix"],
        "impact": (
            "Restarts postfix on this email host only. Mail may pause and retry. "
            "Does not delete the queue, run postsuper, or send mail."
        ),
    },
    "nginx": {
        "label": "Restart nginx",
        "command": EXACT_RESTART_COMMANDS["nginx"],
        "impact": (
            "Restarts nginx on this host only. Open HTTP connections drop briefly. "
            "Does not edit nginx config or restart any other unit."
        ),
    },
    "kong": {
        "label": "Restart Kong",
        "command": EXACT_RESTART_COMMANDS["kong"],
        "impact": (
            "Restarts kong on this host only. API traffic may drop briefly. "
            "Does not edit Kong config, reload other units, or restart the database."
        ),
    },
    "grafana-server": {
        "label": "Restart Grafana",
        "command": EXACT_RESTART_COMMANDS["grafana-server"],
        "impact": (
            "Restarts grafana-server on this host only. The dashboard may be unreachable briefly. "
            "Does not edit Grafana config or restart any other unit."
        ),
    },
}

_DOWN_FLAG = {
    "docker": "docker_active",
    "postfix": "postfix_active",
    "nginx": "nginx_active",
    "kong": "kong_active",
    "grafana-server": "grafana_active",
}


def _confirmed_down(extras: dict[str, Any] | None, flag: str) -> bool:
    """True only when the collector stored an explicit False. Missing is not down."""
    if not extras or flag not in extras:
        return False
    return extras.get(flag) is False


def pick_proposal(
    alert_type: str | None,
    host_collect_error: str | None,
    *,
    server: "Server | None" = None,
    extras: dict[str, Any] | None = None,
) -> tuple[str, dict[str, str]]:
    if (alert_type or "") == "collect_failed" or host_collect_error:
        return "ssh_verify", {}
    unit = recovery_unit(server)
    if unit and _confirmed_down(extras, _DOWN_FLAG[unit]):
        return "systemctl_restart", {"service_name": unit}
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
    if action_key == "systemctl_restart":
        service = (extra_params or {}).get("service_name", "").strip()
        spec = RESTART_SPECS.get(service)
        if spec is None:
            raise ValueError(f"Service '{service}' is not an allowlisted recovery unit.")
        command = spec["command"]
        impact = spec["impact"]
    else:
        command = SAFE_COMMANDS[action_key]["command"]
        impact = SAFE_COMMANDS[action_key]["impact"]
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
    params["proposed_command"] = command
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
    label = (
        RESTART_SPECS[extra["service_name"]]["label"]
        if action_key == "systemctl_restart"
        else SAFE_COMMANDS[action_key]["label"]
    )
    notes = (
        f"Alert: {params['alert_type']}. Reason: {params['alert_reason']}. "
        f"Proposed: {label}. Command: {params['proposed_command']}."
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
