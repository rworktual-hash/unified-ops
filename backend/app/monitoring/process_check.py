"""Read-only process listing. The remote command is fixed; the name is matched in Python."""

from __future__ import annotations

import re

from app.config import settings
from app.monitoring.ssh_client import ssh_session

# Fixed command. Process names are never interpolated into the shell.
CMD_PS_ARGS = "ps -eo args="

PROCESS_NAME_RE = re.compile(r"^[A-Za-z0-9._/: -]{1,128}$")


class ProcessCheckError(Exception):
    pass


def valid_process_name(name: str) -> bool:
    stripped = name.strip()
    if not stripped or stripped != name:
        return False
    if not PROCESS_NAME_RE.fullmatch(stripped):
        return False
    return any(not ch.isspace() for ch in stripped)


def process_in_listing(listing: str, process_name: str) -> bool:
    for line in listing.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == CMD_PS_ARGS or stripped.startswith("ps -eo args"):
            continue
        if process_name in stripped:
            return True
    return False


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
