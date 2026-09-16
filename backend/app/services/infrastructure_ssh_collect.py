from sqlalchemy.orm import Session

from app.models.infrastructure_ssh_snapshot import InfrastructureSshSnapshot
from app.models.server import Server
from app.monitoring.infrastructure_ssh_collectors import (
    collect_infrastructure_ssh_insights,
    should_collect_infrastructure,
)


def collect_and_store_infrastructure_ssh(
    db: Session, server: Server
) -> InfrastructureSshSnapshot | None:
    if not should_collect_infrastructure(server.ip_address, server.project):
        return None
    snap = collect_infrastructure_ssh_insights(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        server_name=server.server_name,
        server_type=server.server_type,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    row = InfrastructureSshSnapshot(
        server_id=server.id,
        collected_at=snap.collected_at,
        role=snap.role,
        service_active=snap.service_active,
        nginx_active=snap.nginx_active,
        kong_active=snap.kong_active,
        docker_active=snap.docker_active,
        redis_role=snap.redis_role,
        redis_connected_clients=snap.redis_connected_clients,
        redis_used_memory_bytes=snap.redis_used_memory_bytes,
        replication_io_running=snap.replication_io_running,
        replication_sql_running=snap.replication_sql_running,
        replica_in_recovery=snap.replica_in_recovery,
        replication_lag_seconds=snap.replication_lag_seconds,
        db_connections=snap.db_connections,
        slow_queries=snap.slow_queries,
        db_uptime_seconds=snap.db_uptime_seconds,
        data_mount=snap.data_mount,
        data_disk_used_pct=snap.data_disk_used_pct,
        data_disk_free_gb=snap.data_disk_free_gb,
        extra_service_status=snap.extra_service_status,
        healthcheck_status=snap.healthcheck_status,
        collect_error=snap.collect_error,
    )
    db.add(row)
    return row
