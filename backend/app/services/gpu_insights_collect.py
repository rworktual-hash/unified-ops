from sqlalchemy.orm import Session

from app.models.gpu_insights_snapshot import GpuInsightsSnapshotRow
from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.monitoring.ai_gpu_insights_collectors import collect_gpu_host_insights
from app.services.gpu_product_collect import gpu_product_collect_enabled


def _gpu_averages(gpu_rows: list[GpuMetric]) -> tuple[float | None, float | None]:
    ok = [g for g in gpu_rows if g.status == "ok" and g.utilization_pct is not None]
    if not ok:
        return None, None
    util = sum(g.utilization_pct for g in ok if g.utilization_pct is not None) / len(ok)
    temps = [g.temperature_c for g in ok if g.temperature_c is not None]
    temp_avg = sum(temps) / len(temps) if temps else None
    return util, temp_avg


def collect_and_store_gpu_insights(
    db: Session,
    server: Server,
    gpu_rows: list[GpuMetric],
) -> GpuInsightsSnapshotRow | None:
    if not gpu_product_collect_enabled(server):
        return None
    snap = collect_gpu_host_insights(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    util_avg, temp_avg = _gpu_averages(gpu_rows)
    row = GpuInsightsSnapshotRow(
        server_id=server.id,
        collected_at=snap.collected_at,
        process_count=snap.process_count,
        tcp_inuse=snap.tcp_inuse,
        tcp_connection_lines=snap.tcp_connection_lines,
        tcp_established=snap.tcp_established,
        listen_sockets=snap.listen_sockets,
        listen_port_8000=snap.listen_port_8000,
        listen_port_8011=snap.listen_port_8011,
        localhost_ping_ok=snap.localhost_ping_ok,
        cpu_util_pct=snap.cpu_util_pct,
        gpu_util_avg=util_avg,
        gpu_temp_avg=temp_avg,
        net_rx_bytes=snap.net_rx_bytes,
        net_tx_bytes=snap.net_tx_bytes,
        collect_error=snap.error,
    )
    db.add(row)
    return row
