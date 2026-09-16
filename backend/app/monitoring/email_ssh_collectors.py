"""Read-only SSH email gateway metrics (no MariaDB, no queue deletes)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.email_collectors import _parse_mailq
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

CMD_MAILQ = "mailq"
CMD_POSTFIX = "systemctl is-active postfix 2>/dev/null || echo inactive"
CMD_DOVECOT = "systemctl is-active dovecot 2>/dev/null || echo inactive"
CMD_OPENDKIM = "systemctl is-active opendkim 2>/dev/null || echo inactive"
CMD_PFLOGSUMM = "pflogsumm -d today 2>/dev/null | head -60"
CMD_RECENT_LOG = (
    "journalctl -u postfix --since today -n 30 --no-pager 2>/dev/null "
    "|| tail -30 /var/log/mail.log 2>/dev/null "
    "|| tail -30 /var/log/maillog 2>/dev/null"
)

_ALLOWED = {CMD_MAILQ, CMD_POSTFIX, CMD_DOVECOT, CMD_OPENDKIM, CMD_PFLOGSUMM, CMD_RECENT_LOG}


def _run(client, command: str) -> tuple[int, str, str]:
    if command not in _ALLOWED:
        raise ValueError("Command not allowed")
    timeout = settings.email_ssh_command_timeout
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out.strip(), err.strip()


def _service_active(out: str) -> bool:
    return out.strip().lower() == "active"


def parse_pflogsumm(text: str) -> dict[str, int]:
    stats: dict[str, int] = {}
    patterns = [
        ("mail_received", r"(\d+)\s+received"),
        ("mail_delivered", r"(\d+)\s+delivered"),
        ("mail_bounced", r"(\d+)\s+bounced"),
        ("mail_rejected", r"(\d+)\s+reject"),
        ("mail_deferred", r"(\d+)\s+deferred"),
    ]
    for key, pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            stats[key] = int(m.group(1))
    return stats


@dataclass
class EmailSshInsights:
    collected_at: datetime
    queue_messages: int | None
    queue_size_kb: int | None
    postfix_active: bool | None
    dovecot_active: bool | None
    opendkim_active: bool | None
    mail_received: int | None
    mail_delivered: int | None
    mail_bounced: int | None
    mail_rejected: int | None
    mail_deferred: int | None
    stats_source: str | None
    recent_log_sample: str | None
    error: str | None = None


def collect_email_ssh_insights(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> EmailSshInsights:
    now = datetime.now(timezone.utc)
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
            postfix_active = dovecot_active = opendkim_active = None
            for cmd, assign in (
                (CMD_POSTFIX, "postfix"),
                (CMD_DOVECOT, "dovecot"),
                (CMD_OPENDKIM, "opendkim"),
            ):
                code, out, err = _run(client, cmd)
                active = _service_active(out) if code == 0 else None
                if assign == "postfix":
                    postfix_active = active
                elif assign == "dovecot":
                    dovecot_active = active
                else:
                    opendkim_active = active
                if code != 0 and active is None:
                    errors.append(f"{assign}: {err or out}")

            queue_messages, queue_kb = None, None
            code, out, err = _run(client, CMD_MAILQ)
            if code == 0:
                queue_messages, queue_kb = _parse_mailq(out)
            else:
                errors.append(f"mailq: {err or out}")

            stats_source = None
            mail_received = mail_delivered = mail_bounced = mail_rejected = mail_deferred = None
            code, out, err = _run(client, CMD_PFLOGSUMM)
            if code == 0 and out and "PFLOGSUMM" not in out:
                parsed = parse_pflogsumm(out)
                if parsed:
                    stats_source = "pflogsumm"
                    mail_received = parsed.get("mail_received")
                    mail_delivered = parsed.get("mail_delivered")
                    mail_bounced = parsed.get("mail_bounced")
                    mail_rejected = parsed.get("mail_rejected")
                    mail_deferred = parsed.get("mail_deferred")

            recent: str | None = None
            code, out, err = _run(client, CMD_RECENT_LOG)
            if code == 0 and out:
                recent = out[:4000]

            return EmailSshInsights(
                collected_at=now,
                queue_messages=queue_messages,
                queue_size_kb=queue_kb,
                postfix_active=postfix_active,
                dovecot_active=dovecot_active,
                opendkim_active=opendkim_active,
                mail_received=mail_received,
                mail_delivered=mail_delivered,
                mail_bounced=mail_bounced,
                mail_rejected=mail_rejected,
                mail_deferred=mail_deferred,
                stats_source=stats_source,
                recent_log_sample=recent,
                error="; ".join(errors) if errors else None,
            )
    except CredentialError as exc:
        return EmailSshInsights(
            collected_at=now,
            queue_messages=None,
            queue_size_kb=None,
            postfix_active=None,
            dovecot_active=None,
            opendkim_active=None,
            mail_received=None,
            mail_delivered=None,
            mail_bounced=None,
            mail_rejected=None,
            mail_deferred=None,
            stats_source=None,
            recent_log_sample=None,
            error=str(exc),
        )


def should_collect_email_ssh_insights(server_ip: str, project: str | None) -> bool:
    if not settings.email_ssh_insights_enabled:
        return False
    if (project or "").lower() != "email":
        return False
    ips = settings.email_ssh_insights_ips_set
    if not ips:
        return True
    return server_ip in ips
