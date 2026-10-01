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
                "id": s.id,
                "name": s.server_name,
                "ip": s.ip_address,
                "ssh_port": s.ssh_port,
                "username": s.ssh_username,
                "type": s.server_type,
                "project": s.project,
                "latest_host_metrics": {
                    "collected_at": host.collected_at.isoformat() if host else None,
                    "mem_used_pct": host.mem_used_pct if host else None,
                    "disk_root_pct": host.disk_root_pct if host else None,
                    "load_1m": host.load_1m if host else None,
                    "collect_error": host.collect_error if host else None,
                },
                "latest_gpu_metrics": [
                    {
                        "gpu_index": g.gpu_index,
                        "utilization_pct": g.utilization_pct,
                        "temperature_c": g.temperature_c,
                        "status": g.status,
                        "mem_used_mb": g.mem_used_mb,
                        "mem_total_mb": g.mem_total_mb,
                    }
                    for g in gpus[:4]
                ],
                "open_alerts": [
                    {
                        "type": a.alert_type,
                        "severity": a.severity,
                        "title": a.title,
                        "message": a.message,
                    }
                    for a in open_alerts
                ],
        }
        email_today = _email_today(email_snaps.get(s.id))
        if email_today is not None:
            entry["latest_email_today"] = email_today
        module = _module_metrics(
            s,
            email_snaps.get(s.id),
            voice_snaps.get(s.id),
            backup_snaps.get(s.id),
            infra_snaps.get(s.id),
        )
        if module is not None:
            entry["module_metrics"] = module
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
        "collected_at": row.collected_at.isoformat() if row.collected_at else None,
        "period": "today",
        "received": row.mail_received,
        "delivered": row.mail_delivered,
        "bounced": row.mail_bounced,
        "rejected": row.mail_rejected,
        "deferred": row.mail_deferred,
        "queue_messages": row.queue_messages,
        "queue_deferred": row.queue_deferred,
        "postfix_active": row.postfix_active,
    }


def _module_metrics(
    server: Server,
    email: EmailSshSnapshot | None,
    voice: VoiceMgSshSnapshot | None,
    backup: BackupVaultSshSnapshot | None,
    infra: InfrastructureSshSnapshot | None,
) -> dict[str, Any] | None:
    project = (server.project or "").lower()
    if project == "email" and email is not None:
        return {
            "module": "email",
            "collected_at": email.collected_at.isoformat() if email.collected_at else None,
            "postfix_active": email.postfix_active,
            "dovecot_active": email.dovecot_active,
            "queue_messages": email.queue_messages,
            "received_today": email.mail_received,
            "delivered_today": email.mail_delivered,
            "bounced_today": email.mail_bounced,
        }
    if project == "voicemg" and voice is not None:
        return {
            "module": "voicemg",
            "collected_at": voice.collected_at.isoformat() if voice.collected_at else None,
            "role": voice.role,
            "service_active": voice.service_active,
            "containers_running": voice.containers_running,
            "app_process_count": voice.app_process_count,
            "disk_used_pct": voice.data_disk_used_pct,
            "services": _clip(voice.extra_service_status),
            "health": _clip(voice.healthcheck_status),
        }
    if project == "backupvault" and backup is not None:
        return {
            "module": "backupvault",
            "collected_at": backup.collected_at.isoformat() if backup.collected_at else None,
            "role": backup.role,
            "service_active": backup.service_active,
            "latest_backup_at": backup.latest_backup_at.isoformat() if backup.latest_backup_at else None,
            "latest_backup_path": _clip(backup.latest_backup_path, 120),
            "backup_file_count": backup.backup_file_count,
            "disk_used_pct": backup.data_disk_used_pct,
            "replication_lag_seconds": backup.replication_lag_seconds,
        }
    if infra is not None:
        return {
            "module": "infrastructure",
            "collected_at": infra.collected_at.isoformat() if infra.collected_at else None,
            "role": infra.role,
            "service_active": infra.service_active,
            "nginx_active": infra.nginx_active,
            "kong_active": infra.kong_active,
            "redis_role": infra.redis_role,
            "db_connections": infra.db_connections,
            "replication_lag_seconds": infra.replication_lag_seconds,
            "disk_used_pct": infra.data_disk_used_pct,
            "services": _clip(infra.extra_service_status),
        }
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
    for event in events[:25]:
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
    return json.dumps(context, indent=2, default=str)
