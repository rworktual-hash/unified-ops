from sqlalchemy.orm import Session

from app.models.backupvault_ssh_snapshot import BackupVaultSshSnapshot
from app.models.server import Server
from app.monitoring.backupvault_ssh_collectors import (
    collect_backupvault_ssh_insights,
    should_collect_backupvault,
)


def collect_and_store_backupvault_ssh(
    db: Session, server: Server
) -> BackupVaultSshSnapshot | None:
    if not should_collect_backupvault(server.ip_address, server.project):
        return None
    snap = collect_backupvault_ssh_insights(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        server_name=server.server_name,
        server_type=server.server_type,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    row = BackupVaultSshSnapshot(
        server_id=server.id,
        collected_at=snap.collected_at,
        role=snap.role,
        service_active=snap.service_active,
        docker_active=snap.docker_active,
        nginx_active=snap.nginx_active,
        cron_active=snap.cron_active,
        containers_running=snap.containers_running,
        container_summary=snap.container_summary,
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
        latest_backup_at=snap.latest_backup_at,
        latest_backup_path=snap.latest_backup_path,
        latest_backup_size_bytes=snap.latest_backup_size_bytes,
        backup_process_count=snap.backup_process_count,
        collect_error=snap.collect_error,
    )
    db.add(row)
    return row
