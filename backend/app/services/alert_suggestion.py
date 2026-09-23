"""Advice for one live MariaDB alert. Nothing here runs a command."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

TEAMS = (
    "AI platform",
    "Email",
    "VoiceMG",
    "BackupVault",
    "Infrastructure",
    "Voice",
    "Ops",
)

_TEAM_BY_KEY = {
    "ai": "AI platform",
    "gpu": "AI platform",
    "email": "Email",
    "voicemg": "VoiceMG",
    "backupvault": "BackupVault",
    "infrastructure": "Infrastructure",
    "infra": "Infrastructure",
    "nginx": "Infrastructure",
    "kong": "Infrastructure",
    "redis": "Infrastructure",
    "mysql": "Infrastructure",
    "postgres": "Infrastructure",
    "postgresql": "Infrastructure",
    "monitoring": "Infrastructure",
    "sip": "Voice",
    "pbx": "Voice",
}

_SYSTEM = """You advise Worktual operators about one open MariaDB alert.
Use the alert and the host facts. You may use general operations knowledge for the likely cause.
Do not invent IPs, metrics, or host names that are not in the facts.
Return only a JSON object with keys why, solution, team, time_estimate.
why: one or two sentences on the likely cause.
solution: the better next step. Prefer recollect or SSH verify. Mention a service restart only if the alert says that service is down, and only for docker, postfix, nginx, kong, or grafana-server. Never suggest reboot, delete, process kill, GPU reset, config edits, or password changes.
team: one of AI platform, Email, VoiceMG, BackupVault, Infrastructure, Voice, Ops. Prefer the host team hint when the alert matches that system.
time_estimate: a short hands-on range such as "15–30 minutes". This is an estimate, not a deadline."""


def team_for_host(project: str | None, server_type: str | None) -> str:
    for key in (project, server_type):
        name = _TEAM_BY_KEY.get((key or "").strip().lower())
        if name:
            return name
    return "Ops"


def snap_team(raw: str | None, hint: str) -> str:
    text = (raw or "").strip()
    if not text:
        return hint
    low = text.lower()
    for name in TEAMS:
        if name.lower() == low or name.lower() in low:
            return name
    return hint


def _clip(value: Any, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].strip()


def parse_suggestion(text: str) -> dict[str, str] | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    why = _clip(data.get("why"))
    solution = _clip(data.get("solution"))
    if not why or not solution:
        return None
    return {
        "why": why,
        "solution": solution,
        "team": _clip(data.get("team"), 80),
        "time_estimate": _clip(data.get("time_estimate"), 80) or "15–30 minutes",
    }


def host_facts(db: Session, alert: dict) -> dict[str, Any]:
    from app.models.server import Server
    from app.models.server_metric import ServerMetric

    server_id = alert.get("inventory_server_id")
    server = db.get(Server, int(server_id)) if server_id else None
    metric = None
    if server is not None:
        metric = (
            db.query(ServerMetric)
            .filter(ServerMetric.server_id == server.id)
            .order_by(ServerMetric.collected_at.desc())
            .first()
        )
    project = server.project if server else None
    server_type = server.server_type if server else None
    return {
        "server_name": (server.server_name if server else None)
        or alert.get("inventory_server_name")
        or alert.get("portal_server_name"),
        "ip_address": (server.ip_address if server else None) or alert.get("ip_address") or "",
        "project": project,
        "server_type": server_type,
        "team_hint": team_for_host(project, server_type),
        "matched": bool(alert.get("matched")),
        "mem_used_pct": metric.mem_used_pct if metric else None,
        "disk_root_pct": metric.disk_root_pct if metric else None,
        "load_1m": metric.load_1m if metric else None,
        "collect_error": metric.collect_error if metric else None,
    }


def fallback_suggestion(alert: dict, facts: dict[str, Any]) -> dict[str, Any]:
    title = _clip(alert.get("title") or "Open alert", 180)
    message = _clip(alert.get("message") or title, 320)
    why = message if message.lower() != title.lower() else title
    return {
        "why": why,
        "solution": (
            "Recollect the host and confirm the alert still matches the live metrics. "
            "If docker, postfix, nginx, Kong, or Grafana is explicitly down, request that "
            "restart in Approvals. Nothing else should be changed from here."
        ),
        "team": facts.get("team_hint") or "Ops",
        "time_estimate": "15–30 minutes",
        "from_model": False,
    }


def suggest_from_text(text: str, alert: dict, facts: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_suggestion(text)
    if parsed is None:
        return fallback_suggestion(alert, facts)
    hint = str(facts.get("team_hint") or "Ops")
    return {
        "why": parsed["why"],
        "solution": parsed["solution"],
        "team": snap_team(parsed.get("team"), hint),
        "time_estimate": parsed["time_estimate"],
        "from_model": True,
    }


def suggest_live_alert(db: Session, alert: dict) -> dict[str, Any]:
    facts = host_facts(db, alert)
    payload = {
        "alert": {
            "title": alert.get("title"),
            "message": alert.get("message"),
            "alert_type": alert.get("alert_type"),
            "severity": alert.get("severity"),
            "hostname": alert.get("hostname"),
        },
        "host": facts,
    }
    try:
        from app.services.llm_client import get_chat_llm

        llm = get_chat_llm()
        response = llm.invoke(
            [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content="Facts JSON:\n" + json.dumps(payload, default=str)[:6000]),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
    except Exception:
        return fallback_suggestion(alert, facts)
    return suggest_from_text(content, alert, facts)
