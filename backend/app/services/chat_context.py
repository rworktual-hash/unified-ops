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
