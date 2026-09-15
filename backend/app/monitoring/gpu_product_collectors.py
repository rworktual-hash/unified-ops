"""Read-only SSH collectors for AI/GPU product metrics (compute workloads, driver, docker)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

# Whitelist only — no writes, restarts, or shell beyond fixed pipelines below.
CMD_GPU_COMPUTE_APPS = (
    "nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory "
    "--format=csv,noheader,nounits"
)
CMD_GPU_NAME_DRIVER = "nvidia-smi --query-gpu=index,name,driver_version --format=csv,noheader"
CMD_DOCKER_RUNNING = "docker ps -q 2>/dev/null | wc -l"

_ALLOWED = frozenset({CMD_GPU_COMPUTE_APPS, CMD_GPU_NAME_DRIVER, CMD_DOCKER_RUNNING})


def _run_command(client, command: str) -> tuple[int, str, str]:
    if command not in _ALLOWED:
        raise ValueError("Command not allowed")
    _stdin, stdout, stderr = client.exec_command(command, timeout=settings.ssh_gpu_command_timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out.strip(), err.strip()


def _parse_compute_apps(text: str) -> tuple[int, float | None, str | None]:
    """Return process count, total used GPU memory (MiB), comma-separated process names (truncated)."""
    if not text.strip():
        return 0, 0.0, None
    names: list[str] = []
    total_mem = 0.0
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or "[Not Supported]" in line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            mem = float(parts[-1])
        except ValueError:
            mem = 0.0
        proc = parts[1] if len(parts) >= 2 else "unknown"
        count += 1
        total_mem += mem
        if proc and proc not in names:
            names.append(proc)
    summary = ", ".join(names[:8]) if names else None
    if summary and len(names) > 8:
        summary = summary + ", …"
    return count, total_mem if count else 0.0, summary


def _parse_name_driver(text: str) -> tuple[str | None, str | None]:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",", 2)]
        if len(parts) >= 3:
            return parts[1][:128], parts[2][:64]
        if len(parts) == 2:
            return parts[1][:128], None
    return None, None


def _parse_docker_count(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    return int(match.group(0))


@dataclass
class GpuProductSnapshot:
    collected_at: datetime
    compute_process_count: int | None
    compute_mem_used_mb: float | None
    compute_process_names: str | None
    docker_containers_running: int | None
    gpu_model_name: str | None
    driver_version: str | None
    error: str | None = None


def collect_gpu_product_snapshot(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> GpuProductSnapshot:
    now = datetime.now(timezone.utc)
    errors: list[str] = []
    compute_count: int | None = None
    compute_mem: float | None = None
    proc_names: str | None = None
    docker_count: int | None = None
    model_name: str | None = None
    driver: str | None = None

    try:
        with ssh_session(
            host=host,
            port=port,
            username=username,
            credential_ref=credential_ref,
            ssh_password=ssh_password,
            ssh_auth_mode=ssh_auth_mode,
        ) as client:
            code, out, err = _run_command(client, CMD_GPU_NAME_DRIVER)
            if code != 0 and not out:
                errors.append(f"gpu_info: {err or f'exit {code}'}"[:500])
            else:
                model_name, driver = _parse_name_driver(out)

            code, out, err = _run_command(client, CMD_GPU_COMPUTE_APPS)
            if code != 0 and not out:
                errors.append(f"compute_apps: {err or f'exit {code}'}"[:500])
            else:
                compute_count, compute_mem, proc_names = _parse_compute_apps(out)
                if proc_names and len(proc_names) > 500:
                    proc_names = proc_names[:497] + "…"

            code, out, err = _run_command(client, CMD_DOCKER_RUNNING)
            if code != 0 and not out.strip().isdigit():
                # docker missing is normal on some hosts
                if "docker" not in (err or "").lower() and code != 0:
                    errors.append(f"docker: {err or f'exit {code}'}"[:200])
            else:
                docker_count = _parse_docker_count(out)

    except CredentialError as exc:
        return GpuProductSnapshot(
            collected_at=now,
            compute_process_count=None,
            compute_mem_used_mb=None,
            compute_process_names=None,
            docker_containers_running=None,
            gpu_model_name=None,
            driver_version=None,
            error=str(exc)[:1000],
        )
    except Exception as exc:
        return GpuProductSnapshot(
            collected_at=now,
            compute_process_count=None,
            compute_mem_used_mb=None,
            compute_process_names=None,
            docker_containers_running=None,
            gpu_model_name=None,
            driver_version=None,
            error=str(exc)[:1000],
        )

    err_text = "; ".join(errors) if errors else None
    return GpuProductSnapshot(
        collected_at=now,
        compute_process_count=compute_count,
        compute_mem_used_mb=compute_mem,
        compute_process_names=proc_names,
        docker_containers_running=docker_count,
        gpu_model_name=model_name,
        driver_version=driver,
        error=err_text,
    )
