"""Read-only SSH collectors for AI GPU host insights (TCP, processes, listen ports, CPU, network)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

CMD_PS_COUNT = "ps -e --no-headers | wc -l"
CMD_SOCKSTAT = "cat /proc/net/sockstat"
CMD_SS_LISTEN = "ss -tlnH 2>/dev/null | wc -l"
CMD_SS_ESTABLISHED = "ss -H -tan state established 2>/dev/null | wc -l"
CMD_SS_TCP_LINES = "ss -H -tan 2>/dev/null | wc -l"
CMD_SS_LISTEN_8000 = "ss -tlnH sport = :8000 2>/dev/null | wc -l"
CMD_CPU_UTIL = "grep '^cpu ' /proc/stat; sleep 1; grep '^cpu ' /proc/stat"
CMD_NET_DEV = "cat /proc/net/dev"

_ALLOWED = frozenset(
    {
        CMD_PS_COUNT,
        CMD_SOCKSTAT,
        CMD_SS_LISTEN,
        CMD_SS_ESTABLISHED,
        CMD_SS_TCP_LINES,
        CMD_SS_LISTEN_8000,
        CMD_CPU_UTIL,
        CMD_NET_DEV,
    }
)


def _run_command(client, command: str) -> tuple[int, str, str]:
    if command not in _ALLOWED:
        raise ValueError("Command not allowed")
    timeout = settings.ssh_gpu_command_timeout if command == CMD_CPU_UTIL else settings.ssh_command_timeout
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out.strip(), err.strip()


def _parse_wc(text: str) -> int | None:
    match = re.search(r"\d+", text.strip())
    return int(match.group(0)) if match else None


def _parse_sockstat_tcp_inuse(text: str) -> int | None:
    for line in text.splitlines():
        if "TCP:" in line:
            match = re.search(r"inuse\s+(\d+)", line)
            if match:
                return int(match.group(1))
    return None


def _parse_cpu_util_two_samples(text: str) -> float | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.startswith("cpu ")]
    if len(lines) < 2:
        return None

    def _idle_total(line: str) -> tuple[float, float] | None:
        parts = line.split()
        if len(parts) < 5:
            return None
        try:
            vals = [float(x) for x in parts[1:]]
        except ValueError:
            return None
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0.0)
        return idle, sum(vals)

    a, b = _idle_total(lines[0]), _idle_total(lines[-1])
    if not a or not b:
        return None
    idle_delta = b[0] - a[0]
    total_delta = b[1] - a[1]
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0))


def _parse_net_dev_bytes(text: str) -> tuple[int | None, int | None]:
    rx_total = 0
    tx_total = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("Inter-") or line.startswith(" face"):
            continue
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        if name == "lo":
            continue
        parts = rest.split()
        if len(parts) < 9:
            continue
        try:
            rx_total += int(parts[0])
            tx_total += int(parts[8])
        except ValueError:
            continue
    return (rx_total if rx_total else None, tx_total if tx_total else None)


@dataclass
class GpuHostInsightsSnapshot:
    collected_at: datetime
    process_count: int | None
    tcp_inuse: int | None
    tcp_connection_lines: int | None
    tcp_established: int | None
    listen_sockets: int | None
    listen_port_8000: int | None
    cpu_util_pct: float | None
    net_rx_bytes: int | None
    net_tx_bytes: int | None
    error: str | None = None


def collect_gpu_host_insights(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> GpuHostInsightsSnapshot:
    now = datetime.now(timezone.utc)
    errors: list[str] = []
    process_count: int | None = None
    tcp_inuse: int | None = None
    tcp_lines: int | None = None
    tcp_established: int | None = None
    listen_sockets: int | None = None
    listen_8000: int | None = None
    cpu_util: float | None = None
    rx: int | None = None
    tx: int | None = None

    try:
        with ssh_session(
            host=host,
            port=port,
            username=username,
            credential_ref=credential_ref,
            ssh_password=ssh_password,
            ssh_auth_mode=ssh_auth_mode,
        ) as client:
            for cmd, parser in (
                (CMD_PS_COUNT, lambda o: _parse_wc(o)),
                (CMD_SOCKSTAT, _parse_sockstat_tcp_inuse),
                (CMD_SS_TCP_LINES, _parse_wc),
                (CMD_SS_ESTABLISHED, _parse_wc),
                (CMD_SS_LISTEN, _parse_wc),
                (CMD_SS_LISTEN_8000, _parse_wc),
            ):
                code, out, err = _run_command(client, cmd)
                if code != 0 and not out.strip():
                    errors.append(f"{cmd[:40]}: {err or code}"[:120])
                    continue
                val = parser(out)
                if cmd == CMD_PS_COUNT:
                    process_count = val
                elif cmd == CMD_SOCKSTAT:
                    tcp_inuse = val
                elif cmd == CMD_SS_TCP_LINES:
                    tcp_lines = val
                elif cmd == CMD_SS_ESTABLISHED:
                    tcp_established = val
                elif cmd == CMD_SS_LISTEN:
                    listen_sockets = val
                elif cmd == CMD_SS_LISTEN_8000:
                    listen_8000 = val

            code, out, err = _run_command(client, CMD_CPU_UTIL)
            if code == 0:
                cpu_util = _parse_cpu_util_two_samples(out)
            else:
                errors.append(f"cpu: {err or code}"[:80])

            code, out, err = _run_command(client, CMD_NET_DEV)
            if code == 0:
                rx, tx = _parse_net_dev_bytes(out)
            else:
                errors.append(f"net: {err or code}"[:80])

    except CredentialError as exc:
        return GpuHostInsightsSnapshot(
            collected_at=now,
            process_count=None,
            tcp_inuse=None,
            tcp_connection_lines=None,
            tcp_established=None,
            listen_sockets=None,
            listen_port_8000=None,
            cpu_util_pct=None,
            net_rx_bytes=None,
            net_tx_bytes=None,
            error=str(exc)[:1000],
        )
    except Exception as exc:
        return GpuHostInsightsSnapshot(
            collected_at=now,
            process_count=None,
            tcp_inuse=None,
            tcp_connection_lines=None,
            tcp_established=None,
            listen_sockets=None,
            listen_port_8000=None,
            cpu_util_pct=None,
            net_rx_bytes=None,
            net_tx_bytes=None,
            error=str(exc)[:1000],
        )

    return GpuHostInsightsSnapshot(
        collected_at=now,
        process_count=process_count,
        tcp_inuse=tcp_inuse,
        tcp_connection_lines=tcp_lines,
        tcp_established=tcp_established,
        listen_sockets=listen_sockets,
        listen_port_8000=listen_8000,
        cpu_util_pct=cpu_util,
        net_rx_bytes=rx,
        net_tx_bytes=tx,
        error="; ".join(errors) if errors else None,
    )
