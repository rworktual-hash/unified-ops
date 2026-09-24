"""Advice for live MariaDB alerts. Nothing here runs a command."""

from __future__ import annotations

import json
import re
import threading
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
why: one short plain sentence a new operator can read. Say what is wrong in everyday words. Example: "The disk is 95% full, so new files may not save."
solution: one short plain sentence for the next step only. Prefer recollect or SSH verify. Example: "Check which files are using the space over SSH, then recollect." Mention a service restart only if the alert says that service is down, and only for docker, postfix, nginx, kong, or grafana-server. Never suggest reboot, delete, process kill, GPU reset, config edits, or password changes.
team: one of AI platform, Email, VoiceMG, BackupVault, Infrastructure, Voice, Ops. Prefer the host team hint when the alert matches that system.
time_estimate: a short hands-on range such as "15–30 minutes". This is an estimate, not a deadline."""

_BATCH_SYSTEM = """You advise Worktual operators about open MariaDB alerts.
Use each alert and its host facts. You may use general operations knowledge for the likely cause.
Do not invent IPs, metrics, or host names that are not in the facts.
Return only JSON: {"suggestions":[{"source_id": number, "why": "...", "solution": "...", "team": "...", "time_estimate": "..."}]}
Include one object for every alert, using that alert's source_id.
why: one short plain sentence a new operator can read. Say what is wrong in everyday words. Example: "The disk is 95% full, so new files may not save."
solution: one short plain sentence for the next step only. Prefer recollect or SSH verify. Example: "Check which files are using the space over SSH, then recollect." Mention a service restart only if the alert says that service is down, and only for docker, postfix, nginx, kong, or grafana-server. Never suggest reboot, delete, process kill, GPU reset, config edits, or password changes.
team: one of AI platform, Email, VoiceMG, BackupVault, Infrastructure, Voice, Ops. Prefer the host team hint when the alert matches that system.
time_estimate: a short hands-on range such as "15–30 minutes". This is an estimate, not a deadline."""

_DEPTH_SYSTEM = """You advise Worktual operators about one open MariaDB alert.
Explain in depth why it happened: the likely chain of events, what on the host would confirm it, and what should not be changed.
Use the alert and the host facts. You may use general operations knowledge.
Do not invent IPs, metrics, or host names that are not in the facts.
Never suggest reboot, delete, process kill, GPU reset, config edits, or password changes.
Return only JSON {"detail": "..."} with 4 to 7 sentences."""

_lock = threading.Lock()
_cache: dict[int, dict[str, Any]] = {}
_depth_cache: dict[int, dict[str, Any]] = {}
_queue: list[dict] = []
_inflight: set[int] = set()
_running = False


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


def _load_json(text: str) -> Any:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    start_obj = raw.find("{")
    start_arr = raw.find("[")
    starts = [n for n in (start_obj, start_arr) if n >= 0]
    if not starts:
        return None
    start = min(starts)
    end = max(raw.rfind("}"), raw.rfind("]"))
    if end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


def suggestion_from_obj(data: dict) -> dict[str, str] | None:
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


def parse_suggestion(text: str) -> dict[str, str] | None:
    data = _load_json(text)
    if not isinstance(data, dict):
        return None
    return suggestion_from_obj(data)


def parse_suggestion_list(text: str) -> list[dict[str, Any]]:
    data = _load_json(text)
    items: list[Any]
    if isinstance(data, dict) and isinstance(data.get("suggestions"), list):
        items = data["suggestions"]
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        one = suggestion_from_obj(data)
        return [one] if one else []
    else:
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict) and suggestion_from_obj(item):
            out.append(item)
    return out


def alert_fingerprint(alert: dict) -> str:
    return "|".join(
        str(alert.get(key) or "")
        for key in ("title", "message", "severity", "alert_type")
    )


def reset_suggestion_cache() -> None:
    global _running
    with _lock:
        _cache.clear()
        _depth_cache.clear()
        _queue.clear()
        _inflight.clear()
        _running = False


def remember(alert: dict, suggestion: dict[str, Any]) -> None:
    source_id = int(alert["source_id"])
    row = dict(suggestion)
    row["source_id"] = source_id
    with _lock:
        _cache[source_id] = {"fp": alert_fingerprint(alert), "suggestion": row}


def ready_and_pending(alerts: list[dict]) -> tuple[list[dict], list[int]]:
    ready: list[dict] = []
    pending: list[int] = []
    with _lock:
        for alert in alerts:
            source_id = int(alert["source_id"])
            hit = _cache.get(source_id)
            if hit and hit["fp"] == alert_fingerprint(alert):
                ready.append(hit["suggestion"])
            else:
                pending.append(source_id)
    return ready, pending


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
            "Recollect this host and check the numbers still match. "
            "If docker, postfix, nginx, Kong, or Grafana is down, request that restart in Approvals."
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


def _invoke(system: str, human: str) -> str:
    from app.services.llm_client import get_chat_llm

    response = get_chat_llm().invoke(
        [SystemMessage(content=system), HumanMessage(content=human)]
    )
    content = response.content
    return content if isinstance(content, str) else str(content)


def _alert_payload(alert: dict, facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": alert.get("source_id"),
        "title": alert.get("title"),
        "message": alert.get("message"),
        "alert_type": alert.get("alert_type"),
        "severity": alert.get("severity"),
        "hostname": alert.get("hostname"),
        "host": facts,
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
        content = _invoke(_SYSTEM, "Facts JSON:\n" + json.dumps(payload, default=str)[:6000])
    except Exception:
        return fallback_suggestion(alert, facts)
    return suggest_from_text(content, alert, facts)


def _rows_for_batch(text: str, alerts: list[dict], facts_by_id: dict[int, dict]) -> list[dict]:
    parsed_by_id: dict[int, dict[str, str]] = {}
    for item in parse_suggestion_list(text):
        try:
            source_id = int(item.get("source_id"))
        except (TypeError, ValueError):
            continue
        parsed = suggestion_from_obj(item)
        if parsed:
            parsed_by_id[source_id] = parsed
    rows: list[dict] = []
    for alert in alerts:
        source_id = int(alert["source_id"])
        facts = facts_by_id.get(source_id) or {"team_hint": "Ops"}
        parsed = parsed_by_id.get(source_id)
        if parsed is None:
            row = fallback_suggestion(alert, facts)
        else:
            row = {
                "why": parsed["why"],
                "solution": parsed["solution"],
                "team": snap_team(parsed.get("team"), str(facts.get("team_hint") or "Ops")),
                "time_estimate": parsed["time_estimate"],
                "from_model": True,
            }
        row["source_id"] = source_id
        rows.append(row)
    return rows


def _fill_batch(alerts: list[dict]) -> list[dict]:
    from app.db.session import SessionLocal

    db = SessionLocal()
    facts_by_id: dict[int, dict] = {}
    try:
        for alert in alerts:
            source_id = int(alert["source_id"])
            try:
                facts_by_id[source_id] = host_facts(db, alert)
            except Exception:
                facts_by_id[source_id] = {"team_hint": "Ops"}
        payload = [_alert_payload(alert, facts_by_id[int(alert["source_id"])]) for alert in alerts]
        content = _invoke(_BATCH_SYSTEM, "Facts JSON:\n" + json.dumps(payload, default=str)[:12000])
        return _rows_for_batch(content, alerts, facts_by_id)
    except Exception:
        return [
            {**fallback_suggestion(alert, facts_by_id.get(int(alert["source_id"])) or {"team_hint": "Ops"}), "source_id": int(alert["source_id"])}
            for alert in alerts
        ]
    finally:
        db.close()


def _worker() -> None:
    global _running
    while True:
        with _lock:
            batch: list[dict] = []
            while _queue and len(batch) < 8:
                batch.append(_queue.pop(0))
            if not batch:
                _running = False
                return
        try:
            rows = _fill_batch(batch)
        except Exception:
            rows = []
        if len(rows) != len(batch):
            rows = [
                {
                    **fallback_suggestion(alert, {"team_hint": "Ops"}),
                    "source_id": int(alert["source_id"]),
                }
                for alert in batch
            ]
        for alert, row in zip(batch, rows):
            remember(alert, row)
        with _lock:
            for alert in batch:
                _inflight.discard(int(alert["source_id"]))


def enqueue_missing(alerts: list[dict]) -> None:
    global _running
    start = False
    with _lock:
        for alert in alerts:
            source_id = int(alert.get("source_id") or 0)
            if source_id <= 0:
                continue
            hit = _cache.get(source_id)
            if hit and hit["fp"] == alert_fingerprint(alert):
                continue
            if source_id in _inflight:
                continue
            _inflight.add(source_id)
            _queue.append(dict(alert))
            start = True
        if start and not _running:
            _running = True
            threading.Thread(target=_worker, name="alert-suggestions", daemon=True).start()


def in_depth_for_alert(db: Session, alert: dict) -> dict[str, Any]:
    source_id = int(alert["source_id"])
    fp = alert_fingerprint(alert)
    with _lock:
        hit = _depth_cache.get(source_id)
        if hit and hit["fp"] == fp:
            return hit["row"]
    facts = host_facts(db, alert)
    detail = ""
    from_model = False
    try:
        content = _invoke(
            _DEPTH_SYSTEM,
            "Facts JSON:\n" + json.dumps(_alert_payload(alert, facts), default=str)[:6000],
        )
        data = _load_json(content)
        if isinstance(data, dict):
            detail = _clip(data.get("detail"), 1600)
            from_model = bool(detail)
    except Exception:
        detail = ""
    if not detail:
        short = fallback_suggestion(alert, facts)
        detail = short["why"]
    row = {"source_id": source_id, "detail": detail, "from_model": from_model}
    with _lock:
        _depth_cache[source_id] = {"fp": fp, "row": row}
    return row
