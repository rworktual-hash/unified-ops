from sqlalchemy.orm import Session

from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.models.server_metric import ServerMetric
from app.models.email_queue_snapshot import EmailQueueSnapshot
from app.monitoring.collectors import collect_gpu_metrics, collect_host_metrics
from app.monitoring.email_collectors import collect_email_queue_snapshot
from app.services.alert_eval import evaluate_alerts


def collect_and_store_metrics(db: Session, server: Server) -> tuple[ServerMetric, list[GpuMetric]]:
    host = collect_host_metrics(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    row = ServerMetric(
        server_id=server.id,
        collected_at=host.collected_at,
        load_1m=host.load_1m,
        load_5m=host.load_5m,
        load_15m=host.load_15m,
        mem_total_mb=host.mem_total_mb,
        mem_used_mb=host.mem_used_mb,
        mem_used_pct=host.mem_used_pct,
        disk_root_used_gb=host.disk_root_used_gb,
        disk_root_total_gb=host.disk_root_total_gb,
        disk_root_pct=host.disk_root_pct,
        uptime_seconds=host.uptime_seconds,
        collect_error=host.error,
    )
    db.add(row)

    if server.project == "email":
        mail = collect_email_queue_snapshot(
            host=server.ip_address,
            port=server.ssh_port,
            username=server.ssh_username,
            credential_ref=server.credential_ref,
            ssh_password=server.ssh_password,
            ssh_auth_mode=server.ssh_auth_mode or "auto",
        )
        db.add(
            EmailQueueSnapshot(
                server_id=server.id,
                collected_at=mail.collected_at,
                queue_messages=mail.queue_messages,
                queue_size_kb=mail.queue_size_kb,
                postfix_active=mail.postfix_active,
                collect_error=mail.error,
            )
        )

    gpu_rows: list[GpuMetric] = []
    if server.server_type == "gpu":
        for snap in collect_gpu_metrics(
            host=server.ip_address,
            port=server.ssh_port,
            username=server.ssh_username,
            credential_ref=server.credential_ref,
            ssh_password=server.ssh_password,
            ssh_auth_mode=server.ssh_auth_mode or "auto",
        ):
            gm = GpuMetric(
                server_id=server.id,
                collected_at=snap.collected_at,
                gpu_index=snap.gpu_index,
                utilization_pct=snap.utilization_pct,
                mem_used_mb=snap.mem_used_mb,
                mem_total_mb=snap.mem_total_mb,
                temperature_c=snap.temperature_c,
                status=snap.status,
                collect_error=snap.error,
            )
            db.add(gm)
            gpu_rows.append(gm)

    db.commit()
    db.refresh(row)
    for g in gpu_rows:
        db.refresh(g)
    evaluate_alerts(db, server, row, gpu_rows)
    return row, gpu_rows


def collect_all_active_servers(db: Session) -> tuple[int, int]:
    """Collect host (and GPU/email queue) metrics for every active inventory row."""
    servers = db.query(Server).filter(Server.is_active.is_(True)).order_by(Server.id).all()
    ok = 0
    failed = 0
    for server in servers:
        try:
            collect_and_store_metrics(db, server)
            ok += 1
        except Exception:
            db.rollback()
            failed += 1
    return ok, failed
