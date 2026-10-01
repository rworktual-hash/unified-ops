import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.email_ssh_snapshot import EmailSshSnapshot
from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.models.server_metric import ServerMetric


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
        if (s.project or "").lower() == "email":
            email_today = _latest_email_today(db, s.id)
            if email_today is not None:
                entry["latest_email_today"] = email_today
        fleet.append(entry)

    context: dict[str, Any] = {"connected_servers": fleet, "server_count": len(fleet)}
    if include_campaign:
        context["email_campaign"] = _email_campaign_summary()
    return context


def _latest_email_today(db: Session, server_id: int) -> dict[str, Any] | None:
    row = (
        db.query(EmailSshSnapshot)
        .filter(EmailSshSnapshot.server_id == server_id)
        .order_by(EmailSshSnapshot.collected_at.desc())
        .first()
    )
    if row is None:
        return None
    if (
        row.mail_received is None
        and row.mail_delivered is None
        and row.queue_messages is None
    ):
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


def _email_campaign_summary() -> dict[str, Any]:
    """Campaign bulk-mail totals only. No addresses, subjects, or log lines."""
    try:
        from app.services.email_portal import fetch_email_extras

        raw = fetch_email_extras(24)
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200], "period_hours": 24}
    totals = raw.get("totals") or {}
    queue = raw.get("queue") or {}
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
    }


def context_to_prompt_block(context: dict[str, Any]) -> str:
    return json.dumps(context, indent=2, default=str)
