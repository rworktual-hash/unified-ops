"""Read-only SSH collectors. Only whitelisted commands are executed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

# Phase 3 guardrail: fixed commands only.
CMD_LOAD = "cat /proc/loadavg"
CMD_MEM = "free -m"
CMD_DISK = "df -P /"
CMD_UPTIME = "cat /proc/uptime"
CMD_GPU = (
    "nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu "
    "--format=csv,noheader,nounits"
)


@dataclass
class HostMetricsSnapshot:
    collected_at: datetime
    load_1m: float | None
    load_5m: float | None
    load_15m: float | None
    mem_total_mb: int | None
    mem_used_mb: int | None
    mem_used_pct: float | None
    disk_root_used_gb: float | None
    disk_root_total_gb: float | None
    disk_root_pct: float | None
    uptime_seconds: float | None
    error: str | None = None


@dataclass
class GpuMetricsSnapshot:
    collected_at: datetime
    gpu_index: int
    utilization_pct: float | None
    mem_used_mb: float | None
    mem_total_mb: float | None
    temperature_c: float | None
    status: str
    error: str | None = None


def _run_command(client, command: str) -> tuple[int, str, str]:
    if command not in {CMD_LOAD, CMD_MEM, CMD_DISK, CMD_UPTIME, CMD_GPU}:
        raise ValueError("Command not allowed")
    timeout = settings.ssh_gpu_command_timeout if command == CMD_GPU else settings.ssh_command_timeout
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out.strip(), err.strip()


def _parse_load(text: str) -> tuple[float | None, float | None, float | None]:
    parts = text.split()
    if len(parts) < 3:
        return None, None, None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None, None, None


def _parse_mem(text: str) -> tuple[int | None, int | None, float | None]:
    for line in text.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            if len(parts) >= 3:
                total, used = int(parts[1]), int(parts[2])
                pct = (used / total * 100.0) if total else None
                return total, used, pct
    return None, None, None


def _parse_disk(text: str) -> tuple[float | None, float | None, float | None]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None, None, None
    parts = lines[1].split()
    if len(parts) < 5:
        return None, None, None
    try:
        total_k = int(parts[1])
        used_k = int(parts[2])
        pct_str = parts[4].rstrip("%")
        return used_k / (1024 * 1024), total_k / (1024 * 1024), float(pct_str)
    except ValueError:
        return None, None, None


def _parse_uptime(text: str) -> float | None:
    parts = text.split()
    if not parts:
        return None
    try:
        return float(parts[0])
    except ValueError:
        return None


def collect_host_metrics(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
) -> HostMetricsSnapshot:
    now = datetime.now(timezone.utc)
    try:
        with ssh_session(
            host=host, port=port, username=username, credential_ref=credential_ref
        ) as client:
            errors: list[str] = []
            load = mem = disk = uptime = (None, None, None)
            uptime_sec = None

            for label, cmd, parser in (
                ("load", CMD_LOAD, _parse_load),
                ("mem", CMD_MEM, _parse_mem),
                ("disk", CMD_DISK, _parse_disk),
            ):
                code, out, err = _run_command(client, cmd)
                if code != 0:
                    errors.append(f"{label}: exit {code} {err or out}")
                    continue
                if label == "load":
                    load = parser(out)
                elif label == "mem":
                    mem = parser(out)
                else:
                    disk = parser(out)

            code, out, err = _run_command(client, CMD_UPTIME)
            if code == 0:
                uptime_sec = _parse_uptime(out)
            else:
                errors.append(f"uptime: exit {code} {err or out}")

            return HostMetricsSnapshot(
                collected_at=now,
                load_1m=load[0],
                load_5m=load[1],
                load_15m=load[2],
                mem_total_mb=mem[0],
                mem_used_mb=mem[1],
                mem_used_pct=mem[2],
                disk_root_used_gb=disk[0],
                disk_root_total_gb=disk[1],
                disk_root_pct=disk[2],
                uptime_seconds=uptime_sec,
                error="; ".join(errors) if errors else None,
            )
    except CredentialError as exc:
        return HostMetricsSnapshot(
            collected_at=now,
            load_1m=None,
            load_5m=None,
            load_15m=None,
            mem_total_mb=None,
            mem_used_mb=None,
            mem_used_pct=None,
            disk_root_used_gb=None,
            disk_root_total_gb=None,
            disk_root_pct=None,
            uptime_seconds=None,
            error=str(exc),
        )


def collect_gpu_metrics(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
) -> list[GpuMetricsSnapshot]:
    now = datetime.now(timezone.utc)
    try:
        with ssh_session(
            host=host, port=port, username=username, credential_ref=credential_ref
        ) as client:
            code, out, err = _run_command(client, CMD_GPU)
            if code != 0:
                msg = err or out or f"exit {code}"
                if "not found" in msg.lower() or "failed" in msg.lower():
                    status = "no_gpu"
                else:
                    status = "error"
                return [
                    GpuMetricsSnapshot(
                        collected_at=now,
                        gpu_index=0,
                        utilization_pct=None,
                        mem_used_mb=None,
                        mem_total_mb=None,
                        temperature_c=None,
                        status=status,
                        error=msg[:500],
                    )
                ]
            rows: list[GpuMetricsSnapshot] = []
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 5:
                    continue
                try:
                    idx = int(parts[0])
                    util = float(parts[1])
                    mem_used = float(parts[2])
                    mem_total = float(parts[3])
                    temp = float(parts[4])
                except ValueError:
                    continue
                rows.append(
                    GpuMetricsSnapshot(
                        collected_at=now,
                        gpu_index=idx,
                        utilization_pct=util,
                        mem_used_mb=mem_used,
                        mem_total_mb=mem_total,
                        temperature_c=temp,
                        status="ok",
                    )
                )
            if not rows:
                return [
                    GpuMetricsSnapshot(
                        collected_at=now,
                        gpu_index=0,
                        utilization_pct=None,
                        mem_used_mb=None,
                        mem_total_mb=None,
                        temperature_c=None,
                        status="no_gpu",
                        error="empty nvidia-smi output",
                    )
                ]
            return rows
    except CredentialError as exc:
        return [
            GpuMetricsSnapshot(
                collected_at=now,
                gpu_index=0,
                utilization_pct=None,
                mem_used_mb=None,
                mem_total_mb=None,
                temperature_c=None,
                status="error",
                error=str(exc),
            )
        ]
