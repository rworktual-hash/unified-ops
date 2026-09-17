"""Strictly read-only SSH metrics for BackupVault app and replica hosts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.service_signal import mysql_service_active, postgres_service_active
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

CMD_STORAGE = (
    "df -Pk / /var/lib/mysql /var/lib/postgresql /backup /backups /var/backups "
    "2>/dev/null | awk 'NR==1 || !seen[$6]++'"
)
CMD_BACKUP_PROCESSES = (
    "pgrep -af '(restic|borg|rsync|rclone|mysqldump|mariadb-dump|pg_dump)' "
    "2>/dev/null | head -10"
)
CMD_DOCKER_ACTIVE = "systemctl is-active docker 2>/dev/null || echo inactive"
CMD_NGINX_ACTIVE = "systemctl is-active nginx 2>/dev/null || echo inactive"
CMD_CRON_ACTIVE = (
    "systemctl is-active cron 2>/dev/null || systemctl is-active crond "
    "2>/dev/null || echo inactive"
)
CMD_DOCKER_STATUS = (
    "docker ps --format '{{.Names}}|{{.Status}}' 2>/dev/null | head -30"
)
CMD_MYSQL_ACTIVE = (
    "systemctl is-active mariadb 2>/dev/null || systemctl is-active mysql "
    "2>/dev/null || systemctl is-active mysqld 2>/dev/null || echo inactive"
)
CMD_MYSQL_REPLICA = (
    "timeout 15s mysql --batch --raw --skip-column-names -e 'SHOW REPLICA STATUS\\G' "
    "2>/dev/null || timeout 15s mysql --batch --raw --skip-column-names "
    "-e 'SHOW SLAVE STATUS\\G' 2>/dev/null"
)
CMD_MYSQL_STATUS = (
    "timeout 15s mysql --batch --raw --skip-column-names -e \"SHOW GLOBAL STATUS WHERE "
    "Variable_name IN ('Threads_connected','Slow_queries','Uptime')\" 2>/dev/null"
)
CMD_POSTGRES_ACTIVE = "systemctl is-active postgresql 2>/dev/null || echo inactive"
CMD_POSTGRES_REPLICA = (
    "timeout 15s sudo -n -u postgres psql -At -c \"SELECT pg_is_in_recovery(),"
    "COALESCE(EXTRACT(EPOCH FROM now()-pg_last_xact_replay_timestamp())::bigint,-1);\" "
    "2>/dev/null"
)
CMD_POSTGRES_CONNECTIONS = (
    "timeout 15s sudo -n -u postgres psql -At -c \"SELECT count(*) FROM pg_stat_activity;\" "
    "2>/dev/null"
)


def _quoted_paths(paths: list[str]) -> str:
    return " ".join(paths)


def configured_backup_paths() -> list[str]:
    return settings.backupvault_backup_paths_list or ["/backup", "/backups", "/var/backups"]


def build_last_backup_cmd(paths: list[str]) -> str:
    return (
        f"timeout 15s find {_quoted_paths(paths)} -maxdepth 4 -type f "
        "-printf '%T@|%s|%p\\n' 2>/dev/null | sort -nr | head -1"
    )


def build_backup_totals_cmd(paths: list[str]) -> str:
    return (
        f"timeout 15s find {_quoted_paths(paths)} -maxdepth 4 -type f "
        "-printf '%s\\n' 2>/dev/null | awk 'BEGIN{n=0;s=0}{n+=1;s+=$1}END{print n\"|\"s}'"
    )


def build_app_service_cmd(unit: str) -> str:
    return f"systemctl is-active {unit} 2>/dev/null || echo inactive"


def build_healthcheck_cmd(url: str) -> str:
    return f"curl -fsS --max-time 5 {url} 2>/dev/null | head -c 400"


def _allowed_commands() -> frozenset[str]:
    commands = {
        CMD_STORAGE,
        CMD_BACKUP_PROCESSES,
        CMD_DOCKER_ACTIVE,
        CMD_NGINX_ACTIVE,
        CMD_CRON_ACTIVE,
        CMD_DOCKER_STATUS,
        CMD_MYSQL_ACTIVE,
        CMD_MYSQL_REPLICA,
        CMD_MYSQL_STATUS,
        CMD_POSTGRES_ACTIVE,
        CMD_POSTGRES_REPLICA,
        CMD_POSTGRES_CONNECTIONS,
        build_last_backup_cmd(configured_backup_paths()),
        build_backup_totals_cmd(configured_backup_paths()),
    }
    for unit in settings.backupvault_app_service_units_list:
        commands.add(build_app_service_cmd(unit))
    for url in settings.backupvault_local_health_urls_list:
        commands.add(build_healthcheck_cmd(url))
    return frozenset(commands)


@dataclass
class BackupVaultSshInsights:
    collected_at: datetime
    role: str
    service_active: bool | None = None
    docker_active: bool | None = None
    nginx_active: bool | None = None
    cron_active: bool | None = None
    containers_running: int | None = None
    container_summary: str | None = None
    replication_io_running: bool | None = None
    replication_sql_running: bool | None = None
    replica_in_recovery: bool | None = None
    replication_lag_seconds: int | None = None
    db_connections: int | None = None
    slow_queries: int | None = None
    db_uptime_seconds: int | None = None
    data_mount: str | None = None
    data_disk_used_pct: float | None = None
    data_disk_free_gb: float | None = None
    latest_backup_at: datetime | None = None
    latest_backup_path: str | None = None
    latest_backup_size_bytes: int | None = None
    backup_file_count: int | None = None
    backup_total_size_bytes: int | None = None
    backup_process_count: int | None = None
    extra_service_status: str | None = None
    healthcheck_status: str | None = None
    collect_error: str | None = None


def _run(client, command: str) -> tuple[int, str, str]:
    if command not in _allowed_commands():
        raise ValueError("Command not allowed")
    _stdin, stdout, stderr = client.exec_command(
        command, timeout=settings.backupvault_ssh_command_timeout
    )
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out, err


def _active(output: str) -> bool:
    return output.strip().lower() == "active"


def parse_storage(output: str) -> tuple[str | None, float | None, float | None]:
    """Select the fullest available non-root data mount, or root as fallback."""
    rows: list[tuple[str, float, float]] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[4].endswith("%"):
            continue
        try:
            used_pct = float(parts[4].rstrip("%"))
            free_gb = int(parts[3]) / 1024 / 1024
        except ValueError:
            continue
        rows.append((parts[5], used_pct, free_gb))
    if not rows:
        return None, None, None
    non_root = [row for row in rows if row[0] != "/"]
    mount, used, free = max(non_root or rows, key=lambda row: row[1])
    return mount, used, round(free, 2)


def parse_mysql_replica(output: str) -> tuple[bool | None, bool | None, int | None]:
    def field(name: str) -> str | None:
        match = re.search(rf"^\s*{re.escape(name)}:\s*(.+?)\s*$", output, re.M)
        return match.group(1) if match else None

    io = field("Replica_IO_Running") or field("Slave_IO_Running")
    sql = field("Replica_SQL_Running") or field("Slave_SQL_Running")
    lag = field("Seconds_Behind_Source") or field("Seconds_Behind_Master")
    return (
        io.lower() == "yes" if io else None,
        sql.lower() == "yes" if sql else None,
        int(lag) if lag and lag.isdigit() else None,
    )


def parse_mysql_status(output: str) -> tuple[int | None, int | None, int | None]:
    values: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            values[parts[0]] = int(parts[1])
    return (
        values.get("Threads_connected"),
        values.get("Slow_queries"),
        values.get("Uptime"),
    )


def parse_postgres_replica(output: str) -> tuple[bool | None, int | None]:
    parts = output.strip().split("|")
    if len(parts) != 2:
        return None, None
    recovery = parts[0].lower() in {"t", "true"}
    lag = int(parts[1]) if parts[1].lstrip("-").isdigit() else None
    return recovery, None if lag is not None and lag < 0 else lag


def parse_latest_backup(
    output: str,
) -> tuple[datetime | None, int | None, str | None]:
    parts = output.split("|", 2)
    if len(parts) != 3:
        return None, None, None
    try:
        when = datetime.fromtimestamp(float(parts[0]), timezone.utc)
        size = int(parts[1])
    except ValueError:
        return None, None, None
    return when, size, parts[2][:1024]


def parse_backup_totals(output: str) -> tuple[int | None, int | None]:
    parts = output.strip().split("|")
    if len(parts) != 2:
        return None, None
    count = int(parts[0]) if parts[0].isdigit() else None
    total = int(parts[1]) if parts[1].isdigit() else None
    return count, total


def _common_metrics(client, result: BackupVaultSshInsights, errors: list[str]) -> None:
    backup_paths = configured_backup_paths()
    code, out, err = _run(client, CMD_STORAGE)
    if code == 0:
        result.data_mount, result.data_disk_used_pct, result.data_disk_free_gb = parse_storage(out)
    else:
        errors.append(f"storage: {err or out}")

    code, out, _err = _run(client, build_last_backup_cmd(backup_paths))
    if code == 0 and out:
        result.latest_backup_at, result.latest_backup_size_bytes, result.latest_backup_path = (
            parse_latest_backup(out)
        )

    code, out, _err = _run(client, build_backup_totals_cmd(backup_paths))
    if code == 0 and out:
        result.backup_file_count, result.backup_total_size_bytes = parse_backup_totals(out)

    code, out, _err = _run(client, CMD_BACKUP_PROCESSES)
    if code == 0:
        result.backup_process_count = len([line for line in out.splitlines() if line.strip()])
    elif code == 1:
        result.backup_process_count = 0


def collect_backupvault_ssh_insights(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    server_name: str,
    server_type: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> BackupVaultSshInsights:
    lower_name = server_name.lower()
    role = (
        "postgres"
        if "postgres" in lower_name
        else "mysql"
        if (server_type or "").lower() == "database"
        else "app"
    )
    result = BackupVaultSshInsights(collected_at=datetime.now(timezone.utc), role=role)
    errors: list[str] = []
    try:
        with ssh_session(
            host=host,
            port=port,
            username=username,
            credential_ref=credential_ref,
            ssh_password=ssh_password,
            ssh_auth_mode=ssh_auth_mode,
        ) as client:
            _common_metrics(client, result, errors)
            if role == "mysql":
                code, out, _err = _run(client, CMD_MYSQL_ACTIVE)
                systemd_ok = _active(out) if code == 0 else None
                code, out, _err = _run(client, CMD_MYSQL_REPLICA)
                if code == 0 and out:
                    (
                        result.replication_io_running,
                        result.replication_sql_running,
                        result.replication_lag_seconds,
                    ) = parse_mysql_replica(out)
                code, out, _err = _run(client, CMD_MYSQL_STATUS)
                if code == 0 and out:
                    (
                        result.db_connections,
                        result.slow_queries,
                        result.db_uptime_seconds,
                    ) = parse_mysql_status(out)
                result.service_active = mysql_service_active(
                    systemd_ok=systemd_ok,
                    db_connections=result.db_connections,
                    db_uptime_seconds=result.db_uptime_seconds,
                )
                if systemd_ok is False and result.service_active:
                    note = "systemd: unit name mismatch"
                    result.extra_service_status = (
                        f"{result.extra_service_status} · {note}"
                        if result.extra_service_status
                        else note
                    )
                elif result.service_active is False:
                    errors.append("mysql: no systemd or SQL status")
            elif role == "postgres":
                code, out, _err = _run(client, CMD_POSTGRES_ACTIVE)
                systemd_ok = _active(out) if code == 0 else None
                code, out, _err = _run(client, CMD_POSTGRES_REPLICA)
                if code == 0 and out:
                    result.replica_in_recovery, result.replication_lag_seconds = (
                        parse_postgres_replica(out)
                    )
                code, out, _err = _run(client, CMD_POSTGRES_CONNECTIONS)
                if code == 0 and out.isdigit():
                    result.db_connections = int(out)
                result.service_active = postgres_service_active(
                    systemd_ok=systemd_ok,
                    db_connections=result.db_connections,
                )
                if systemd_ok is False and result.service_active:
                    note = "systemd: unit name mismatch"
                    result.extra_service_status = (
                        f"{result.extra_service_status} · {note}"
                        if result.extra_service_status
                        else note
                    )
                elif result.service_active is False:
                    errors.append("postgres: no systemd or connection probe")
            else:
                for command, attr in (
                    (CMD_DOCKER_ACTIVE, "docker_active"),
                    (CMD_NGINX_ACTIVE, "nginx_active"),
                    (CMD_CRON_ACTIVE, "cron_active"),
                ):
                    code, out, _err = _run(client, command)
                    setattr(result, attr, _active(out) if code == 0 else None)
                code, out, _err = _run(client, CMD_DOCKER_STATUS)
                if code == 0:
                    lines = [line for line in out.splitlines() if line.strip()]
                    result.containers_running = len(lines)
                    result.container_summary = "\n".join(lines)[:4000] or None
                extra_services: list[str] = []
                extra_up = False
                for unit in settings.backupvault_app_service_units_list:
                    code, out, _err = _run(client, build_app_service_cmd(unit))
                    is_up = code == 0 and _active(out)
                    extra_up = extra_up or is_up
                    label = "Running" if is_up else "Check failed"
                    extra_services.append(f"{unit}: {label}")
                if extra_services:
                    result.extra_service_status = " · ".join(extra_services)[:4000]
                health_rows: list[str] = []
                health_ok = False
                for url in settings.backupvault_local_health_urls_list:
                    code, out, err = _run(client, build_healthcheck_cmd(url))
                    if code == 0 and out:
                        health_rows.append(f"{url}: OK")
                        health_ok = True
                    else:
                        health_rows.append(f"{url}: fail")
                if health_rows:
                    result.healthcheck_status = " · ".join(health_rows)[:4000]
                if (result.containers_running or 0) > 0 or extra_up or health_ok:
                    result.service_active = True
                elif (
                    result.docker_active is False
                    and result.nginx_active is False
                    and not extra_up
                    and not health_ok
                ):
                    result.service_active = False
    except CredentialError as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    result.collect_error = "; ".join(errors) if errors else None
    return result


def should_collect_backupvault(server_ip: str, project: str | None) -> bool:
    if not settings.backupvault_ssh_insights_enabled:
        return False
    if (project or "").lower() != "backupvault":
        return False
    allowed = settings.backupvault_ssh_insights_ips_set
    return not allowed or server_ip in allowed
