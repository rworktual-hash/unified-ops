"""Strictly read-only SSH metrics for infrastructure hosts (nginx, kong, DB, redis, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.backupvault_ssh_collectors import (
    CMD_DOCKER_ACTIVE,
    CMD_DOCKER_STATUS,
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
DEFAULT_PBX_UNITS: tuple[str, ...] = (
    "asterisk",
    "freeswitch",
    "freepbx",
    "pbx",
    "ccaas-pbx",
)
DEFAULT_SIP_UNITS: tuple[str, ...] = (
    "kamailio",
    "opensips",
    "rtpengine",
    "rtpproxy",
    "sgw",
)
CMD_PBX_PROCESSES = (
    "pgrep -af '(asterisk|freeswitch|freepbx|pbx)' 2>/dev/null | head -6"
)
CMD_SIP_PROCESSES = (
    "pgrep -af '(kamailio|opensips|rtpengine|rtpproxy|sip)' 2>/dev/null | head -6"
)


def pbx_service_units() -> list[str]:
    configured = settings.infrastructure_pbx_service_units_list
    return configured if configured else list(DEFAULT_PBX_UNITS)


def sip_service_units() -> list[str]:
    configured = settings.infrastructure_sip_service_units_list
    return configured if configured else list(DEFAULT_SIP_UNITS)


def evaluate_telephony_service(
    *,
    unit_up: list[bool],
    process_count: int | None,
    docker_active: bool | None,
    containers_running: int | None,
) -> bool | None:
    if any(unit_up):
        return True
    if process_count is not None and process_count > 0:
        return True
    if docker_active and containers_running is not None and containers_running > 0:
        return True
    if unit_up:
        return False
    return None


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
        CMD_PBX_PROCESSES,
        CMD_SIP_PROCESSES,
        CMD_DOCKER_ACTIVE,
        CMD_DOCKER_STATUS,
        CMD_MYSQL_ACTIVE,
        CMD_MYSQL_REPLICA,
        CMD_MYSQL_STATUS,
        CMD_POSTGRES_ACTIVE,
        CMD_POSTGRES_REPLICA,
        CMD_POSTGRES_CONNECTIONS,
    }
    for unit in (
        settings.infrastructure_app_service_units_list
        + pbx_service_units()
        + sip_service_units()
    ):
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


def _merge_extra_status(result: InfrastructureSshInsights, fragment: str) -> None:
    if not fragment:
        return
    if result.extra_service_status:
        result.extra_service_status = f"{result.extra_service_status} · {fragment}"[:4000]
    else:
        result.extra_service_status = fragment[:4000]


def _extra_units(client, result: InfrastructureSshInsights) -> None:
    extra: list[str] = []
    for unit in settings.infrastructure_app_service_units_list:
        code, out, _err = _run(client, build_app_service_cmd(unit))
        label = "Running" if code == 0 and _active(out) else "Check failed"
        extra.append(f"{unit}: {label}")
    if extra:
        _merge_extra_status(result, " · ".join(extra))


def _collect_telephony(
    client,
    result: InfrastructureSshInsights,
    *,
    role: str,
    errors: list[str],
) -> None:
    units = pbx_service_units() if role == "pbx" else sip_service_units()
    proc_cmd = CMD_PBX_PROCESSES if role == "pbx" else CMD_SIP_PROCESSES
    unit_rows: list[str] = []
    unit_up: list[bool] = []

    code, out, _err = _run(client, CMD_DOCKER_ACTIVE)
    result.docker_active = _active(out) if code == 0 else None

    code, out, _err = _run(client, CMD_DOCKER_STATUS)
    containers = 0
    if code == 0:
        lines = [line for line in out.splitlines() if line.strip()]
        containers = len(lines)

    for unit in units:
        code, out, _err = _run(client, build_app_service_cmd(unit))
        up = code == 0 and _active(out)
        unit_up.append(up)
        unit_rows.append(f"{unit}: {'Running' if up else 'Check failed'}")

    process_count: int | None = None
    code, out, _err = _run(client, proc_cmd)
    if code == 0:
        lines = [line for line in out.splitlines() if line.strip()]
        process_count = len(lines)
    elif code == 1:
        process_count = 0

    if unit_rows:
        _merge_extra_status(result, " · ".join(unit_rows))
    if process_count is not None:
        _merge_extra_status(result, f"{process_count} voice procs")

    result.service_active = evaluate_telephony_service(
        unit_up=unit_up,
        process_count=process_count,
        docker_active=result.docker_active,
        containers_running=containers if containers else None,
    )
    if result.service_active is False and not any(unit_up) and process_count == 0:
        errors.append(f"{role}: no systemd unit active and no matching processes")


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
            elif role in {"pbx", "sip"}:
                _collect_telephony(client, result, role=role, errors=errors)
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
