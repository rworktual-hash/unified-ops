"""Strictly read-only SSH metrics for VoiceMG / STT / VMG application hosts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.backupvault_ssh_collectors import (
    CMD_DOCKER_ACTIVE,
    CMD_DOCKER_STATUS,
    CMD_NGINX_ACTIVE,
    build_app_service_cmd,
    build_healthcheck_cmd,
    parse_storage,
)
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

CMD_STORAGE = "df -Pk / /opt /var/lib/docker 2>/dev/null | awk 'NR==1 || !seen[$6]++'"
CMD_APP_PROCESSES = (
    "pgrep -af '(voicemg|voice-mg|ccaas-vmg|/vmg|stt|whisper|triton|faster-whisper)' "
    "2>/dev/null | head -8"
)
CMD_NVIDIA_SUMMARY = (
    "nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total "
    "--format=csv,noheader 2>/dev/null | head -8"
)


def _role(server_name: str) -> str:
    lower = server_name.lower()
    if "stt" in lower:
        return "stt"
    return "vmg"


def _service_units_for_role(role: str) -> list[str]:
    common = settings.voicemg_app_service_units_list
    if role == "stt":
        return common + settings.voicemg_stt_service_units_list
    return common + settings.voicemg_vmg_service_units_list


def _allowed_commands() -> frozenset[str]:
    commands = {
        CMD_STORAGE,
        CMD_DOCKER_ACTIVE,
        CMD_NGINX_ACTIVE,
        CMD_DOCKER_STATUS,
        CMD_APP_PROCESSES,
        CMD_NVIDIA_SUMMARY,
    }
    for unit in (
        settings.voicemg_app_service_units_list
        + settings.voicemg_vmg_service_units_list
        + settings.voicemg_stt_service_units_list
    ):
        commands.add(build_app_service_cmd(unit))
    for url in settings.voicemg_local_health_urls_list:
        commands.add(build_healthcheck_cmd(url))
    return frozenset(commands)


@dataclass
class VoiceMgSshInsights:
    collected_at: datetime
    role: str
    service_active: bool | None = None
    docker_active: bool | None = None
    nginx_active: bool | None = None
    containers_running: int | None = None
    container_summary: str | None = None
    app_process_count: int | None = None
    app_process_sample: str | None = None
    gpu_device_count: int | None = None
    gpu_util_summary: str | None = None
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
        command, timeout=settings.voicemg_ssh_command_timeout
    )
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out, err


def _active(output: str) -> bool:
    return output.strip().lower() == "active"


def parse_nvidia_summary(output: str) -> tuple[int | None, str | None]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None, None
    return len(lines), "\n".join(lines)[:2000]


def collect_voicemg_ssh_insights(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    server_name: str,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> VoiceMgSshInsights:
    role = _role(server_name)
    result = VoiceMgSshInsights(collected_at=datetime.now(timezone.utc), role=role)
    errors: list[str] = []
    unit_states: list[bool] = []
    try:
        with ssh_session(
            host=host,
            port=port,
            username=username,
            credential_ref=credential_ref,
            ssh_password=ssh_password,
            ssh_auth_mode=ssh_auth_mode,
        ) as client:
            code, out, err = _run(client, CMD_STORAGE)
            if code == 0:
                result.data_mount, result.data_disk_used_pct, result.data_disk_free_gb = (
                    parse_storage(out)
                )
            else:
                errors.append(f"storage: {err or out}")

            for command, attr in (
                (CMD_DOCKER_ACTIVE, "docker_active"),
                (CMD_NGINX_ACTIVE, "nginx_active"),
            ):
                code, out, _err = _run(client, command)
                setattr(result, attr, _active(out) if code == 0 else None)

            code, out, _err = _run(client, CMD_DOCKER_STATUS)
            if code == 0:
                lines = [line for line in out.splitlines() if line.strip()]
                result.containers_running = len(lines)
                result.container_summary = "\n".join(lines)[:4000] or None

            code, out, _err = _run(client, CMD_APP_PROCESSES)
            if code == 0:
                lines = [line for line in out.splitlines() if line.strip()]
                result.app_process_count = len(lines)
                result.app_process_sample = "\n".join(lines)[:2000] or None
            elif code == 1:
                result.app_process_count = 0

            if role == "stt":
                code, out, _err = _run(client, CMD_NVIDIA_SUMMARY)
                if code == 0 and out:
                    result.gpu_device_count, result.gpu_util_summary = parse_nvidia_summary(out)

            extra: list[str] = []
            for unit in _service_units_for_role(role):
                code, out, _err = _run(client, build_app_service_cmd(unit))
                is_up = code == 0 and _active(out)
                unit_states.append(is_up)
                extra.append(f"{unit}: {'Running' if is_up else 'Check failed'}")
            if extra:
                result.extra_service_status = " · ".join(extra)[:4000]

            health_rows: list[str] = []
            for url in settings.voicemg_local_health_urls_list:
                code, out, err = _run(client, build_healthcheck_cmd(url))
                if code == 0 and out:
                    health_rows.append(f"{url}: OK")
                else:
                    health_rows.append(f"{url}: fail")
                    if err:
                        errors.append(f"healthcheck {url}: {err}")
            if health_rows:
                result.healthcheck_status = " · ".join(health_rows)[:4000]

            if unit_states:
                result.service_active = any(unit_states)
            elif result.containers_running and result.containers_running > 0:
                result.service_active = True
            elif result.app_process_count is not None and result.app_process_count > 0:
                result.service_active = True
            elif result.docker_active is False:
                result.service_active = False
    except CredentialError as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    result.collect_error = "; ".join(errors) if errors else None
    return result


def should_collect_voicemg(server_ip: str, project: str | None) -> bool:
    if not settings.voicemg_ssh_insights_enabled:
        return False
    if (project or "").lower() != "voicemg":
        return False
    allowed = settings.voicemg_ssh_insights_ips_set
    return not allowed or server_ip in allowed
