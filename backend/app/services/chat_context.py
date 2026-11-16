import json
from typing import Any

from sqlalchemy.orm import Session

from sqlalchemy import func

from app.models.alert import Alert
from app.models.backupvault_ssh_snapshot import BackupVaultSshSnapshot
from app.models.email_ssh_snapshot import EmailSshSnapshot
from app.models.gpu_metric import GpuMetric
from app.models.infrastructure_ssh_snapshot import InfrastructureSshSnapshot
from app.models.server import Server
from app.models.server_metric import ServerMetric
from app.models.voicemg_ssh_snapshot import VoiceMgSshSnapshot


def build_ops_context(
    db: Session,
    *,
    server_ids: list[int] | None = None,
    include_campaign: bool = False,
) -> dict[str, Any]:
    q = db.query(Server).filter(Server.is_active.is_(True))
    if server_ids:
        q = q.filter(Server.id.in_(server_ids))
    servers = q.order_by(Server.id).all()
    server_ids = [s.id for s in servers]
    email_snaps = _latest_rows(db, EmailSshSnapshot, server_ids)
    voice_snaps = _latest_rows(db, VoiceMgSshSnapshot, server_ids)
    backup_snaps = _latest_rows(db, BackupVaultSshSnapshot, server_ids)
    infra_snaps = _latest_rows(db, InfrastructureSshSnapshot, server_ids)

    fleet: list[dict[str, Any]] = []
    for s in servers:
        host = (
            db.query(ServerMetric)
            .filter(ServerMetric.server_id == s.id)
            .order_by(ServerMetric.collected_at.desc())
            .first()
        )
        gpus = (
            db.query(GpuMetric)
            .filter(GpuMetric.server_id == s.id)
            .order_by(GpuMetric.collected_at.desc())
            .limit(8)
            .all()
        )
        open_alerts = (
            db.query(Alert)
            .filter(Alert.server_id == s.id, Alert.status == "open")
            .order_by(Alert.last_seen_at.desc())
            .limit(10)
            .all()
        )
        entry: dict[str, Any] = {
            "name": s.server_name,
            "ip": s.ip_address,
            "type": s.server_type,
            "project": s.project,
            "mem": _round(host.mem_used_pct if host else None),
            "disk": _round(host.disk_root_pct if host else None),
            "load": _round(host.load_1m if host else None),
        }
        if host and host.collect_error:
            entry["collect_error"] = _clip(host.collect_error, 80)
        gpu_bits = [
            f"{g.gpu_index}:{_round(g.utilization_pct)}%/{_round(g.temperature_c)}C"
            for g in gpus[:2]
            if g.utilization_pct is not None or g.temperature_c is not None
        ]
        if gpu_bits:
            entry["gpu"] = gpu_bits
        alert_bits = [
            f"{a.severity}: {_clip(a.title, 48)}"
            for a in open_alerts[:2]
        ]
        if alert_bits:
            entry["alerts"] = alert_bits
        email_today = _email_today(email_snaps.get(s.id))
        if email_today is not None:
            entry["email_today"] = email_today
        module = _module_metrics(
            s,
            email_snaps.get(s.id),
            voice_snaps.get(s.id),
            backup_snaps.get(s.id),
            infra_snaps.get(s.id),
        )
        if module is not None:
            entry["module"] = module
        fleet.append(entry)

    context: dict[str, Any] = {"connected_servers": fleet, "server_count": len(fleet)}
    if include_campaign:
        context["email_campaign"] = _email_campaign_summary()
    return context


def _latest_rows(db: Session, model: type, server_ids: list[int]) -> dict[int, Any]:
    if not server_ids:
        return {}
    latest = (
        db.query(model.server_id, func.max(model.id).label("mid"))
        .filter(model.server_id.in_(server_ids))
        .group_by(model.server_id)
        .subquery()
    )
    rows = db.query(model).join(latest, model.id == latest.c.mid).all()
    return {row.server_id: row for row in rows}


def _round(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number >= 10:
        return int(round(number))
    return round(number, 1)


def _clip(value: Any, limit: int = 180) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _email_today(row: EmailSshSnapshot | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if row.mail_received is None and row.mail_delivered is None and row.queue_messages is None:
        return None
    return {
        "delivered": row.mail_delivered,
        "received": row.mail_received,
        "bounced": row.mail_bounced,
    }


def _module_metrics(
    server: Server,
    email: EmailSshSnapshot | None,
    voice: VoiceMgSshSnapshot | None,
    backup: BackupVaultSshSnapshot | None,
    infra: InfrastructureSshSnapshot | None,
) -> str | None:
    project = (server.project or "").lower()
    if project == "voicemg" and voice is not None:
        return (
            f"voicemg {voice.role} service={voice.service_active} "
            f"procs={voice.app_process_count} disk={_round(voice.data_disk_used_pct)}"
        )
    if project == "backupvault" and backup is not None:
        when = backup.latest_backup_at.isoformat() if backup.latest_backup_at else "none"
        return (
            f"backupvault {backup.role} service={backup.service_active} "
            f"files={backup.backup_file_count} latest={when} disk={_round(backup.data_disk_used_pct)}"
        )
    if project == "email" and email is not None:
        return f"email postfix={email.postfix_active} queue={email.queue_messages}"
    if infra is not None:
        return (
            f"infra {infra.role} service={infra.service_active} nginx={infra.nginx_active} "
            f"kong={infra.kong_active} redis={infra.redis_role} db_conn={infra.db_connections} "
            f"lag_s={infra.replication_lag_seconds}"
        )
    return None


def _email_campaign_summary() -> dict[str, Any]:
    """Campaign totals plus the recent log rows the Email page already loaded."""
    try:
        from app.services.email_portal import fetch_email_extras

        raw = fetch_email_extras(24)
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200], "period_hours": 24, "recent_messages": []}
    totals = raw.get("totals") or {}
    queue = raw.get("queue") or {}
    recent: list[dict[str, Any]] = []
    events = list(raw.get("events") or [])
    events.sort(key=lambda row: 0 if str(row.get("status") or "").lower() in {"sent", "delivered"} else 1)
    for event in events[:12]:
        recent.append(
            {
                "time": event.get("occurred_at"),
                "status": event.get("status"),
                "from": event.get("from_addr"),
                "to": event.get("to_addr"),
                "subject": _clip(event.get("subject"), 80),
                "server": event.get("inventory_name") or event.get("server_name"),
            }
        )
    return {
        "ok": bool(raw.get("ok")),
        "reason": raw.get("reason"),
        "period_hours": raw.get("period_hours") or 24,
        "sent": totals.get("sent"),
        "delivered": totals.get("delivered"),
        "bounce": totals.get("bounce"),
        "deferred": totals.get("deferred"),
        "inbound": totals.get("inbound"),
        "outbound": totals.get("outbound"),
        "failed": totals.get("failed"),
        "log_total": totals.get("log_total"),
        "campaign_queued": totals.get("campaign_queued"),
        "queue_count": queue.get("queue_count"),
        "queue_deferred": queue.get("deferred_count"),
        "recent_messages": recent,
    }


def context_to_prompt_block(context: dict[str, Any]) -> str:
    return json.dumps(context, separators=(",", ":"), default=str)


def _wants(message: str, words: tuple[str, ...]) -> bool:
    text = message.lower()
    return any(word in text for word in words)


def wants_studio(message: str) -> bool:
    return _wants(message, ("ai studio", "customer", "skill", "token", "mcp", "llm trace", "llm observability"))


def wants_voicemg(message: str) -> bool:
    return _wants(message, ("voicemg", "voice mg", "active call", "rtp", "mos"))


def wants_ai_insights(message: str) -> bool:
    return _wants(message, ("ai insight", "ai insights", "health score"))


def wants_backupvault(message: str) -> bool:
    return _wants(message, ("backupvault", "backup vault"))


def voicemg_answer() -> str:
    """Latest VoiceMG rows from MariaDB 10.180.1.222, the same read the VoiceMG page uses."""
    try:
        from app.services.voicemg_portal import fetch_voicemg_extras

        raw = fetch_voicemg_extras()
    except Exception as exc:
        return f"VoiceMG on MariaDB 10.180.1.222 is unavailable: {exc}."
    if not raw.get("ok"):
        reason = raw.get("reason") or "the portal database is not connected"
        return f"VoiceMG on MariaDB 10.180.1.222 is unavailable: {reason}."
    servers = list(raw.get("servers") or [])
    calls = sum(int(row.get("active_calls") or 0) for row in servers)
    lines = []
    for row in servers[:8]:
        lines.append(
            f"{row.get('hostname') or row.get('ip')}: {int(row.get('active_calls') or 0)} active calls, "
            f"loss {row.get('packet_loss_pct') if row.get('packet_loss_pct') is not None else '—'}%, "
            f"MOS {row.get('mos') if row.get('mos') is not None else '—'}"
        )
    detail = "; ".join(lines) if lines else "no servers in the portal."
    return (
        f"VoiceMG from MariaDB 10.180.1.222: {len(servers)} servers, {calls} active calls. {detail}."
    )


def ai_insights_answer() -> str:
    """Latest AI Insights rows from MariaDB 10.180.1.222."""
    try:
        from app.services.ai_insights_portal import fetch_ai_insights_extras

        raw = fetch_ai_insights_extras()
    except Exception as exc:
        return f"AI Insights on MariaDB 10.180.1.222 is unavailable: {exc}."
    if not raw.get("ok"):
        reason = raw.get("reason") or "the portal database is not connected"
        return f"AI Insights on MariaDB 10.180.1.222 is unavailable: {reason}."
    servers = list(raw.get("servers") or [])
    alerts = sum(int(row.get("open_alerts") or 0) for row in servers)
    lines = []
    for row in servers[:8]:
        lines.append(
            f"{row.get('server_name')}: health {row.get('health_score') if row.get('health_score') is not None else '—'} "
            f"({row.get('health_status') or 'unknown'}), gpu {row.get('gpu_utilization') if row.get('gpu_utilization') is not None else '—'}%"
        )
    detail = "; ".join(lines) if lines else "no servers in the portal."
    return (
        f"AI Insights from MariaDB 10.180.1.222: {len(servers)} servers, {alerts} open alerts. {detail}."
    )


def backupvault_answer() -> str:
    """Latest BackupVault monitoring rows from MariaDB 10.180.1.222."""
    try:
        from app.services.legacy_metrics_sync import fetch_backupvault_monitoring

        raw = fetch_backupvault_monitoring()
    except Exception as exc:
        return f"BackupVault on MariaDB 10.180.1.222 is unavailable: {exc}."
    if not raw.get("ok"):
        reason = raw.get("reason") or "the portal database is not connected"
        return f"BackupVault on MariaDB 10.180.1.222 is unavailable: {reason}."
    return (
        "BackupVault from MariaDB 10.180.1.222: "
        f"{raw.get('db_count') or 0} database servers, {raw.get('nfs_count') or 0} NFS servers, "
        f"{raw.get('db_with_snapshot') or 0} with a snapshot."
    )


def studio_answer(db: Session) -> str:
    """Customer, agent, skill, and token totals from AI Studio traces stored here."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy.exc import OperationalError

    from app.models.llm_obs import LlmObsRun, LlmObsTrace

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        traces = (
            db.query(LlmObsTrace)
            .filter(LlmObsTrace.started_at >= since)
            .order_by(LlmObsTrace.started_at.desc())
            .limit(200)
            .all()
        )
    except OperationalError as exc:
        return f"AI Studio traces are unavailable: {exc}."
    if not traces:
        return "AI Studio has no requests in the last 24 hours. A request appears after AI Studio sends a customer chat."
    trace_ids = [row.id for row in traces]
    runs = db.query(LlmObsRun).filter(LlmObsRun.trace_id.in_(trace_ids)).all()
    skills: list[str] = []
    tokens = 0
    by_trace: dict[int, list] = {}
    for run in runs:
        by_trace.setdefault(run.trace_id, []).append(run)
        if run.run_type == "skill" and run.name not in skills:
            skills.append(run.name)
        if run.run_type == "llm" and run.total_tokens:
            tokens += run.total_tokens
    customers = []
    agents = []
    for row in traces:
        if row.customer and row.customer not in customers:
            customers.append(row.customer)
        if row.agent_name and row.agent_name not in agents:
            agents.append(row.agent_name)
    recent = []
    for row in traces[:5]:
        skill_names = [run.name for run in by_trace.get(row.id, []) if run.run_type == "skill"]
        recent.append(
            f"{row.customer or 'unknown customer'} · {row.agent_name or 'agent'} · "
            f"{', '.join(skill_names) or 'no skill'} · {row.status}"
        )
    return (
        f"AI Studio in the last 24 hours: {len(traces)} requests, {tokens} tokens. "
        f"Customers: {', '.join(customers) or 'none'}. "
        f"Agents: {', '.join(agents) or 'none'}. "
        f"Skills: {', '.join(skills) or 'none'}. "
        f"Latest: {'; '.join(recent)}."
    )
