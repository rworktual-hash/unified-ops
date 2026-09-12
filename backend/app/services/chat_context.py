import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.models.server_metric import ServerMetric


def build_ops_context(db: Session, *, server_ids: list[int] | None = None) -> dict[str, Any]:
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
        fleet.append(
            {
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
        )

    return {"connected_servers": fleet, "server_count": len(fleet)}


def context_to_prompt_block(context: dict[str, Any]) -> str:
    return json.dumps(context, indent=2, default=str)
