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
from app.monitoring.service_signal import mysql_service_active, postgres_service_active
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

DEFAULT_KONG_UNITS: tuple[str, ...] = ("kong", "kong.service", "kong-gateway")
DEFAULT_GRAFANA_UNITS: tuple[str, ...] = ("grafana-server", "grafana")

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
DEFAULT_REDIS_UNITS: tuple[str, ...] = (
    "redis",
    "redis-server",
    "redis@6379",
)
DEFAULT_REDIS_CLI_PROBES: tuple[str, ...] = (
    "default",
    "/var/run/redis/redis.sock",
    "/run/redis/redis.sock",
    "127.0.0.1:6379",
)
CMD_REDIS_PROCESSES = "pgrep -af 'redis-server' 2>/dev/null | head -6"
CMD_REDIS_DOCKER = (
    "docker ps --format '{{.Names}}|{{.Status}}' 2>/dev/null | grep -i redis | head -5"
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


def redis_service_units() -> list[str]:
    configured = settings.infrastructure_redis_service_units_list
    return configured if configured else list(DEFAULT_REDIS_UNITS)


def redis_cli_probes() -> list[str]:
    configured = settings.infrastructure_redis_cli_probes_list
    return configured if configured else list(DEFAULT_REDIS_CLI_PROBES)


def kong_service_units() -> list[str]:
    configured = settings.infrastructure_kong_service_units_list
    return configured if configured else list(DEFAULT_KONG_UNITS)


def grafana_service_units() -> list[str]:
    configured = settings.infrastructure_grafana_service_units_list
    return configured if configured else list(DEFAULT_GRAFANA_UNITS)


def redis_cli_args_from_probe(probe: str) -> str:
    if probe in {"", "default"}:
        return ""
    if probe.startswith("/"):
        return f"-s {probe}"
    if ":" in probe:
        host, port = probe.split(":", 1)
        if host in {"127.0.0.1", "localhost"} and port.isdigit():
            host_flag = "127.0.0.1" if host == "localhost" else host
            return f"-h {host_flag} -p {port}"
    return ""


def build_redis_ping_cmd(probe: str) -> str:
    args = redis_cli_args_from_probe(probe)
    if not args:
        return "timeout 5 redis-cli ping 2>/dev/null || echo FAIL"
    return f"timeout 5 redis-cli {args} ping 2>/dev/null || echo FAIL"


def build_redis_info_cmd(probe: str) -> str:
    args = redis_cli_args_from_probe(probe)
    grep = (
        "grep -E '^(role:|connected_clients:|used_memory:|maxmemory:|master_link_status:)'"
    )
    if not args:
        return f"timeout 5 redis-cli INFO 2>/dev/null | {grep}"
    return f"timeout 5 redis-cli {args} INFO 2>/dev/null | {grep}"


def evaluate_redis_service(
    *,
    unit_up: list[bool],
    pong_ok: bool,
    process_count: int | None,
    docker_redis_containers: int | None,
) -> bool | None:
    if pong_ok:
        return True
    if any(unit_up):
        return True
    if process_count is not None and process_count > 0:
        return True
    if docker_redis_containers is not None and docker_redis_containers > 0:
        return True
    if unit_up or process_count == 0:
        return False
    return None


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
        CMD_REDIS_PROCESSES,
        CMD_REDIS_DOCKER,
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
        + redis_service_units()
        + kong_service_units()
        + grafana_service_units()
    ):
        commands.add(build_app_service_cmd(unit))
    for probe in redis_cli_probes():
        commands.add(build_redis_ping_cmd(probe))
        commands.add(build_redis_info_cmd(probe))
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


def _probe_systemd_units(
    client,
    units: list[str],
) -> tuple[bool | None, str | None]:
    if not units:
        return None, None
    rows: list[str] = []
    any_up = False
    for unit in units:
        code, out, _err = _run(client, build_app_service_cmd(unit))
        up = code == 0 and _active(out)
        any_up = any_up or up
        rows.append(f"{unit}: {'Running' if up else 'Check failed'}")
    active: bool | None = True if any_up else False
    return active, " · ".join(rows)


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


def _collect_redis(
    client,
    result: InfrastructureSshInsights,
    errors: list[str],
) -> None:
    unit_rows: list[str] = []
    unit_up: list[bool] = []
    pong_ok = False
    winning_probe: str | None = None

    code, out, _err = _run(client, CMD_DOCKER_ACTIVE)
    result.docker_active = _active(out) if code == 0 else None

    for unit in redis_service_units():
        code, out, _err = _run(client, build_app_service_cmd(unit))
        up = code == 0 and _active(out)
        unit_up.append(up)
        unit_rows.append(f"{unit}: {'Running' if up else 'Check failed'}")

    probe_rows: list[str] = []
    for probe in redis_cli_probes():
        cmd = build_redis_ping_cmd(probe)
        code, out, err = _run(client, cmd)
        label = probe if probe != "default" else "cli default"
        if code == 0 and out.strip().upper() == "PONG":
            pong_ok = True
            probe_rows.append(f"ping {label}: PONG")
            if winning_probe is None:
                winning_probe = probe
        else:
            probe_rows.append(f"ping {label}: fail")

    process_count: int | None = None
    code, out, _err = _run(client, CMD_REDIS_PROCESSES)
    if code == 0:
        lines = [line for line in out.splitlines() if line.strip()]
        process_count = len(lines)
    elif code == 1:
        process_count = 0

    docker_redis = 0
    code, out, _err = _run(client, CMD_REDIS_DOCKER)
    if code == 0 and out.strip():
        docker_redis = len([line for line in out.splitlines() if line.strip()])

    if winning_probe is not None:
        code, out, _err = _run(client, build_redis_info_cmd(winning_probe))
        if code == 0 and out:
            result.redis_role, result.redis_connected_clients, result.redis_used_memory_bytes = (
                parse_redis_info(out)
            )

    if unit_rows:
        _merge_extra_status(result, " · ".join(unit_rows))
    if probe_rows:
        if not pong_ok and (any(unit_up) or (process_count or 0) > 0 or docker_redis > 0):
            _merge_extra_status(result, "cli: no PONG (auth/socket/port)")
        else:
            _merge_extra_status(result, " · ".join(probe_rows))
    if process_count is not None:
        _merge_extra_status(result, f"{process_count} redis procs")
    if docker_redis:
        _merge_extra_status(result, f"{docker_redis} redis container(s)")

    result.service_active = evaluate_redis_service(
        unit_up=unit_up,
        pong_ok=pong_ok,
        process_count=process_count,
        docker_redis_containers=docker_redis,
    )
    if result.service_active is False:
        errors.append("redis: no unit, process, container, or PONG signal")


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
                active, detail = _probe_systemd_units(client, kong_service_units())
                result.kong_active = active
                result.service_active = active
                if detail:
                    _merge_extra_status(result, detail)
                if active is False:
                    code, out, err = _run(client, CMD_KONG_ACTIVE)
                    if code == 0 and _active(out):
                        result.kong_active = True
                        result.service_active = True
            elif role == "mysql":
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
                    _merge_extra_status(result, "systemd: unit name mismatch")
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
                    _merge_extra_status(result, "systemd: unit name mismatch")
                elif result.service_active is False:
                    errors.append("postgres: no systemd or connection probe")
            elif role == "redis":
                _collect_redis(client, result, errors)
            elif role == "monitoring":
                active, detail = _probe_systemd_units(client, grafana_service_units())
                result.service_active = active
                if detail:
                    _merge_extra_status(result, detail)
                if active is False:
                    errors.append("grafana: no matching systemd unit")
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
    if result.service_active is True and errors:
        errors = [
            err
            for err in errors
            if not err.startswith(
                ("mysql:", "postgres:", "redis:", "grafana:", "kong:", "nginx:", "kafka:", "pbx:", "sip:")
            )
        ]
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
