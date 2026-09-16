from sqlalchemy.orm import Session

from app.models.server import Server
from app.models.voicemg_ssh_snapshot import VoiceMgSshSnapshot
from app.monitoring.voicemg_ssh_collectors import (
    collect_voicemg_ssh_insights,
    should_collect_voicemg,
)


def collect_and_store_voicemg_ssh(db: Session, server: Server) -> VoiceMgSshSnapshot | None:
    if not should_collect_voicemg(server.ip_address, server.project):
        return None
    snap = collect_voicemg_ssh_insights(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        server_name=server.server_name,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    row = VoiceMgSshSnapshot(
        server_id=server.id,
        collected_at=snap.collected_at,
        role=snap.role,
        service_active=snap.service_active,
        docker_active=snap.docker_active,
        nginx_active=snap.nginx_active,
        containers_running=snap.containers_running,
        container_summary=snap.container_summary,
        app_process_count=snap.app_process_count,
        app_process_sample=snap.app_process_sample,
        gpu_device_count=snap.gpu_device_count,
        gpu_util_summary=snap.gpu_util_summary,
        data_mount=snap.data_mount,
        data_disk_used_pct=snap.data_disk_used_pct,
        data_disk_free_gb=snap.data_disk_free_gb,
        extra_service_status=snap.extra_service_status,
        healthcheck_status=snap.healthcheck_status,
        collect_error=snap.collect_error,
    )
    db.add(row)
    return row
