"""Strictly read-only SSH metrics for infrastructure hosts (nginx, kong, DB, redis, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.backupvault_ssh_collectors import (
    CMD_MYSQL_ACTIVE,
    CMD_MYSQL_REPLICA,
    CMD_MYSQL_STATUS,
    CMD_POSTGRES_ACTIVE,
    CMD_POSTGRES_CONNECTIONS,
    CMD_POSTGRES_REPLICA,
    build_app_service_cmd,
    build_healthcheck_cmd,
    parse_mysql_replica,
    parse_mysql_status,
    parse_postgres_replica,
    parse_storage,
)
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

CMD_STORAGE = (
    "df -Pk / /var/lib/mysql /var/lib/postgresql /var/lib/redis "
    "2>/dev/null | awk 'NR==1 || !seen[$6]++'"
)
CMD_NGINX_ACTIVE = "systemctl is-active nginx 2>/dev/null || echo inactive"
CMD_KONG_ACTIVE = "systemctl is-active kong 2>/dev/null || echo inactive"
CMD_DOCKER_ACTIVE = "systemctl is-active docker 2>/dev/null || echo inactive"
CMD_GRAFANA_ACTIVE = (
    "systemctl is-active grafana-server 2>/dev/null || echo inactive"
)
CMD_KAFKA_ACTIVE = (
    "systemctl is-active kafka 2>/dev/null || systemctl is-active kafka-server "
    "2>/dev/null || echo inactive"
)
CMD_REDIS_PING = "timeout 5 redis-cli ping 2>/dev/null || echo FAIL"
CMD_REDIS_INFO = (
    "timeout 5 redis-cli INFO 2>/dev/null | grep -E "
    "'^(role:|connected_clients:|used_memory:|maxmemory:|master_link_status:)'"
)
CMD_PBX_ACTIVE = (
    "systemctl is-active asterisk 2>/dev/null || systemctl is-active freeswitch "
    "2>/dev/null || echo inactive"
)
CMD_SIP_ACTIVE = (
    "systemctl is-active kamailio 2>/dev/null || systemctl is-active opensips "
    "2>/dev/null || echo inactive"
)


def _role(server_name: str, server_type: str | None) -> str:
    lower = server_name.lower()
    st = (server_type or "").lower()
    if "postgres" in lower or "postgresql" in lower:
        return "postgres"
    if st == "database":
        return "mysql"
    if "kafka" in lower:
        return "kafka"
    if st in {"nginx", "kong", "redis", "monitoring", "pbx", "sip", "infra"}:
        return st
    return st or "generic"


def _allowed_commands() -> frozenset[str]:
    commands = {
        CMD_STORAGE,
        CMD_NGINX_ACTIVE,
        CMD_KONG_ACTIVE,
        CMD_DOCKER_ACTIVE,
        CMD_GRAFANA_ACTIVE,
        CMD_KAFKA_ACTIVE,
        CMD_REDIS_PING,
        CMD_REDIS_INFO,
        CMD_PBX_ACTIVE,
        CMD_SIP_ACTIVE,
        CMD_MYSQL_ACTIVE,
        CMD_MYSQL_REPLICA,
        CMD_MYSQL_STATUS,
        CMD_POSTGRES_ACTIVE,
        CMD_POSTGRES_REPLICA,
        CMD_POSTGRES_CONNECTIONS,
    }
    for unit in settings.infrastructure_app_service_units_list:
        commands.add(build_app_service_cmd(unit))
    for url in settings.infrastructure_local_health_urls_list:
        commands.add(build_healthcheck_cmd(url))
    return frozenset(commands)


@dataclass
class InfrastructureSshInsights:
    collected_at: datetime
    role: str
    service_active: bool | None = None
    nginx_active: bool | None = None
    kong_active: bool | None = None
    docker_active: bool | None = None
    redis_role: str | None = None
    redis_connected_clients: int | None = None
    redis_used_memory_bytes: int | None = None
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
    extra_service_status: str | None = None
    healthcheck_status: str | None = None
    collect_error: str | None = None


def _run(client, command: str) -> tuple[int, str, str]:
    if command not in _allowed_commands():
        raise ValueError("Command not allowed")
    _stdin, stdout, stderr = client.exec_command(
        command, timeout=settings.infrastructure_ssh_command_timeout
    )
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out, err


def _active(output: str) -> bool:
    return output.strip().lower() == "active"


def parse_redis_info(output: str) -> tuple[str | None, int | None, int | None]:
    role: str | None = None
    clients: int | None = None
    used_mem: int | None = None
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "role":
            role = val
        elif key == "connected_clients" and val.isdigit():
            clients = int(val)
        elif key == "used_memory" and val.isdigit():
            used_mem = int(val)
    return role, clients, used_mem


def _storage(client, result: InfrastructureSshInsights, errors: list[str]) -> None:
    code, out, err = _run(client, CMD_STORAGE)
    if code == 0:
        result.data_mount, result.data_disk_used_pct, result.data_disk_free_gb = parse_storage(out)
    else:
        errors.append(f"storage: {err or out}")


def _healthchecks(client, result: InfrastructureSshInsights, errors: list[str]) -> None:
    rows: list[str] = []
    for url in settings.infrastructure_local_health_urls_list:
        code, out, err = _run(client, build_healthcheck_cmd(url))
        if code == 0 and out:
            rows.append(f"{url}: OK")
        else:
            rows.append(f"{url}: fail")
            if err:
                errors.append(f"healthcheck {url}: {err}")
    if rows:
        result.healthcheck_status = " · ".join(rows)[:4000]


def _extra_units(client, result: InfrastructureSshInsights) -> None:
    extra: list[str] = []
    for unit in settings.infrastructure_app_service_units_list:
        code, out, _err = _run(client, build_app_service_cmd(unit))
        label = "Healthy" if code == 0 and _active(out) else "Down"
        extra.append(f"{unit}: {label}")
    if extra:
        result.extra_service_status = " · ".join(extra)[:4000]


def collect_infrastructure_ssh_insights(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    server_name: str,
    server_type: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> InfrastructureSshInsights:
    role = _role(server_name, server_type)
    result = InfrastructureSshInsights(collected_at=datetime.now(timezone.utc), role=role)
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
            _storage(client, result, errors)
            if role == "nginx":
                code, out, err = _run(client, CMD_NGINX_ACTIVE)
                result.nginx_active = _active(out) if code == 0 else None
                result.service_active = result.nginx_active
                if code != 0:
                    errors.append(f"nginx: {err or out}")
            elif role == "kafka":
                code, out, err = _run(client, CMD_KAFKA_ACTIVE)
                result.service_active = _active(out) if code == 0 else None
                if code != 0:
                    errors.append(f"kafka: {err or out}")
                code, out, _err = _run(client, CMD_NGINX_ACTIVE)
                result.nginx_active = _active(out) if code == 0 else None
            elif role == "kong":
                code, out, err = _run(client, CMD_KONG_ACTIVE)
                result.kong_active = _active(out) if code == 0 else None
                result.service_active = result.kong_active
                if code != 0:
                    errors.append(f"kong: {err or out}")
            elif role == "mysql":
                code, out, err = _run(client, CMD_MYSQL_ACTIVE)
                result.service_active = _active(out) if code == 0 else None
                if code != 0:
                    errors.append(f"mysql: {err or out}")
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
            elif role == "postgres":
                code, out, err = _run(client, CMD_POSTGRES_ACTIVE)
                result.service_active = _active(out) if code == 0 else None
                if code != 0:
                    errors.append(f"postgres: {err or out}")
                code, out, _err = _run(client, CMD_POSTGRES_REPLICA)
                if code == 0 and out:
                    result.replica_in_recovery, result.replication_lag_seconds = (
                        parse_postgres_replica(out)
                    )
                code, out, _err = _run(client, CMD_POSTGRES_CONNECTIONS)
                if code == 0 and out.isdigit():
                    result.db_connections = int(out)
            elif role == "redis":
                code, out, err = _run(client, CMD_REDIS_PING)
                result.service_active = out.strip().upper() == "PONG" if code == 0 else None
                if code != 0 or out.strip().upper() != "PONG":
                    errors.append(f"redis ping: {err or out}")
                code, out, _err = _run(client, CMD_REDIS_INFO)
                if code == 0 and out:
                    result.redis_role, result.redis_connected_clients, result.redis_used_memory_bytes = (
                        parse_redis_info(out)
                    )
            elif role == "monitoring":
                code, out, err = _run(client, CMD_GRAFANA_ACTIVE)
                result.service_active = _active(out) if code == 0 else None
                if code != 0:
                    errors.append(f"grafana: {err or out}")
            elif role == "pbx":
                code, out, err = _run(client, CMD_PBX_ACTIVE)
                result.service_active = _active(out) if code == 0 else None
                if code != 0:
                    errors.append(f"pbx: {err or out}")
            elif role == "sip":
                code, out, err = _run(client, CMD_SIP_ACTIVE)
                result.service_active = _active(out) if code == 0 else None
                if code != 0:
                    errors.append(f"sip: {err or out}")
            else:
                code, out, _err = _run(client, CMD_DOCKER_ACTIVE)
                result.docker_active = _active(out) if code == 0 else None
                result.service_active = result.docker_active

            _extra_units(client, result)
            _healthchecks(client, result, errors)
    except CredentialError as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    result.collect_error = "; ".join(errors) if errors else None
    return result


def should_collect_infrastructure(server_ip: str, project: str | None) -> bool:
    if not settings.infrastructure_ssh_insights_enabled:
        return False
    proj = (project or "").lower()
    if proj not in {"infrastructure", "infra"}:
        return False
    allowed = settings.infrastructure_ssh_insights_ips_set
    return not allowed or server_ip in allowed
