"""Read-only process lookup. pgrep is tried first; ps is the fallback."""

from __future__ import annotations

import re

from app.config import settings
from app.monitoring.ssh_client import ssh_session

# Fixed command. Process names are never interpolated into the shell.
CMD_PS_ARGS = "ps -eo pid=,args="
_PGREP_UNAVAILABLE = "__PGREP_UNAVAILABLE__"

PROCESS_NAME_RE = re.compile(r"^[A-Za-z0-9._/: -]{1,128}$")
_PID_LINE = re.compile(r"^(\d+)\s+(.*)$")


class ProcessCheckError(Exception):
    pass


def valid_process_name(name: str) -> bool:
    stripped = name.strip()
    if not stripped or stripped != name:
        return False
    if not PROCESS_NAME_RE.fullmatch(stripped):
        return False
    return any(not ch.isspace() for ch in stripped)


def _is_ps_command(text: str) -> bool:
    stripped = text.strip()
    return stripped == CMD_PS_ARGS or stripped.startswith("ps -eo ")


def matching_pids(listing: str, process_name: str) -> list[str]:
    """PIDs whose command line contains the name. An empty string means a match without a PID."""
    found: list[str] = []
    for line in listing.splitlines():
        stripped = line.strip()
        if not stripped or _is_ps_command(stripped):
            continue
        match = _PID_LINE.match(stripped)
        if match:
            pid, args = match.group(1), match.group(2).strip()
            if _is_ps_command(args):
                continue
            if process_name in args:
                found.append(pid)
            continue
        if process_name in stripped:
            found.append("")
    return found


def format_pids(pids: list[str]) -> str:
    real = [pid for pid in pids if pid]
    if not real:
        return ""
    shown = real[:12]
    text = ", ".join(shown)
    extra = len(real) - len(shown)
    if extra:
        text = f"{text} +{extra}"
    return text[:255]


def process_in_listing(listing: str, process_name: str) -> bool:
    return bool(matching_pids(listing, process_name))


def pgrep_command(process_name: str) -> str:
    """Exact-name lookup. The name is quoted only after it passes validation."""
    if not valid_process_name(process_name):
        raise ProcessCheckError("Process name is invalid")
    quoted = '"' + process_name + '"'
    return (
        "if ! command -v pgrep >/dev/null 2>&1; then "
        f"printf '%s\\n' {_PGREP_UNAVAILABLE}; "
        "else "
        f"pgrep -x {quoted} 2>/dev/null | awk 'NR==1 {{print $1}}'; "
        "fi"
    )


def interpret_pgrep(output: str) -> tuple[str, str]:
    """Return (pid|down|unavailable, pid). Empty pgrep output means the process is down."""
    text = output.strip()
    if _PGREP_UNAVAILABLE in text:
        return ("unavailable", "")
    if not text:
        return ("down", "")
    first = text.splitlines()[0].strip()
    if first.isdigit():
        return ("pid", first)
    return ("unavailable", "")


def fetch_exact_pid(
    *,
    host: str,
    port: int,
    username: str,
    ssh_password: str,
    process_name: str,
) -> tuple[str, str]:
    command = pgrep_command(process_name)
    try:
        with ssh_session(
            host=host,
            port=port,
            username=username,
            credential_ref=None,
            ssh_password=ssh_password,
            ssh_auth_mode="password",
        ) as client:
            _stdin, stdout, _stderr = client.exec_command(command, timeout=settings.ssh_command_timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            stdout.channel.recv_exit_status()
    except Exception as exc:
        raise ProcessCheckError(str(exc) or "SSH failed") from exc
    return interpret_pgrep(out)


def fetch_process_listing(
    *,
    host: str,
    port: int,
    username: str,
    ssh_password: str,
) -> str:
    try:
        with ssh_session(
            host=host,
            port=port,
            username=username,
            credential_ref=None,
            ssh_password=ssh_password,
            ssh_auth_mode="password",
        ) as client:
            _stdin, stdout, stderr = client.exec_command(CMD_PS_ARGS, timeout=settings.ssh_command_timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace").strip()
            code = stdout.channel.recv_exit_status()
    except Exception as exc:
        raise ProcessCheckError(str(exc) or "SSH failed") from exc
    if code != 0:
        detail = err or out.strip() or f"ps exited {code}"
        raise ProcessCheckError(detail[:500])
    return out
