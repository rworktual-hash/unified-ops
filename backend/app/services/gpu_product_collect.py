from sqlalchemy.orm import Session

from app.config import settings
from app.models.gpu_product_snapshot import GpuProductSnapshotRow
from app.models.server import Server
from app.monitoring.gpu_product_collectors import collect_gpu_product_snapshot


def gpu_product_collect_enabled(server: Server) -> bool:
    if server.server_type != "gpu":
        return False
    ips = settings.gpu_product_collect_ips.strip()
    if not ips:
        return False
    if ips == "*":
        return True
    allowed = {p.strip() for p in ips.split(",") if p.strip()}
    return server.ip_address in allowed


def collect_and_store_gpu_product(db: Session, server: Server) -> GpuProductSnapshotRow | None:
    if not gpu_product_collect_enabled(server):
        return None
    snap = collect_gpu_product_snapshot(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    row = GpuProductSnapshotRow(
        server_id=server.id,
        collected_at=snap.collected_at,
        compute_process_count=snap.compute_process_count,
        compute_mem_used_mb=snap.compute_mem_used_mb,
        compute_process_names=snap.compute_process_names,
        docker_containers_running=snap.docker_containers_running,
        docker_active=snap.docker_active,
        docker_container_status=snap.docker_container_status,
        process_sample=snap.process_sample,
        log_tail=snap.log_tail,
        gpu_model_name=snap.gpu_model_name,
        driver_version=snap.driver_version,
        collect_error=snap.error,
    )
    db.add(row)
    return row
