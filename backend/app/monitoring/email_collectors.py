"""Read-only SSH collectors for mail servers (Postfix queue)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

CMD_MAILQ = "mailq"
CMD_POSTFIX = "systemctl is-active postfix 2>/dev/null || echo inactive"

_ALLOWED = {CMD_MAILQ, CMD_POSTFIX}


def _run_command(client, command: str) -> tuple[int, str, str]:
    if command not in _ALLOWED:
        raise ValueError("Command not allowed")
    _stdin, stdout, stderr = client.exec_command(command, timeout=settings.ssh_command_timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out.strip(), err.strip()


def _parse_mailq(text: str) -> tuple[int | None, int | None]:
    """Parse postfix mailq summary line: '-- 5 Kbytes in 2 Requests.'"""
    if "Mail queue is empty" in text:
        return 0, 0
    match = re.search(r"--\s+(\d+)\s+Kbytes?\s+in\s+(\d+)\s+Request", text, re.I)
    if not match:
        return None, None
    return int(match.group(2)), int(match.group(1))


@dataclass
class EmailQueueSnapshot:
    collected_at: datetime
    queue_messages: int | None
    queue_size_kb: int | None
    postfix_active: bool | None
    error: str | None = None


def collect_email_queue_snapshot(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> EmailQueueSnapshot:
    now = datetime.now(timezone.utc)
    try:
        with ssh_session(
            host=host,
            port=port,
            username=username,
            credential_ref=credential_ref,
            ssh_password=ssh_password,
            ssh_auth_mode=ssh_auth_mode,
        ) as client:
            errors: list[str] = []
            postfix_active: bool | None = None
            code, out, err = _run_command(client, CMD_POSTFIX)
            if code == 0:
                postfix_active = out.strip() == "active"
            else:
                errors.append(f"postfix: {err or out}")

            queue_messages, queue_kb = None, None
            code, out, err = _run_command(client, CMD_MAILQ)
            if code == 0:
                queue_messages, queue_kb = _parse_mailq(out)
            else:
                errors.append(f"mailq: {err or out}")

            return EmailQueueSnapshot(
                collected_at=now,
                queue_messages=queue_messages,
                queue_size_kb=queue_kb,
                postfix_active=postfix_active,
                error="; ".join(errors) if errors else None,
            )
    except CredentialError as exc:
        return EmailQueueSnapshot(
            collected_at=now,
            queue_messages=None,
            queue_size_kb=None,
            postfix_active=None,
            error=str(exc),
        )
