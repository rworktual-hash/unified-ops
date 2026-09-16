"""Read-only SSH email gateway metrics (strict allowlist — no queue deletes or config writes)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.monitoring.email_collectors import _parse_mailq
from app.monitoring.ssh_client import ssh_session
from app.services.credentials import CredentialError

# --- Allowlisted commands only (documented in docs/EMAIL_METRICS.md) ---
CMD_MAILQ = "mailq"
CMD_POSTFIX = "systemctl is-active postfix 2>/dev/null || echo inactive"
CMD_DOVECOT = "systemctl is-active dovecot 2>/dev/null || echo inactive"
CMD_OPENDKIM = "systemctl is-active opendkim 2>/dev/null || echo inactive"
CMD_AMAVIS = (
    "systemctl is-active amavis 2>/dev/null || systemctl is-active amavisd 2>/dev/null "
    "|| systemctl is-active amavisd-new 2>/dev/null || echo inactive"
)
CMD_CLAMAV = (
    "systemctl is-active clamav-daemon 2>/dev/null || systemctl is-active clamd 2>/dev/null "
    "|| echo inactive"
)
CMD_PFLOGSUMM = "pflogsumm -d today 2>/dev/null | head -60"
CMD_QUEUE_DIRS = (
    "bash -c 'a=$(find /var/spool/postfix/active -type f 2>/dev/null|wc -l); "
    "d=$(find /var/spool/postfix/deferred -type f 2>/dev/null|wc -l); "
    "h=$(find /var/spool/postfix/hold -type f 2>/dev/null|wc -l); "
    "echo active=$a deferred=$d hold=$h'"
)
CMD_LOG_REJECT = (
    "journalctl -u postfix --since today --no-pager 2>/dev/null "
    "| grep -ciE ' reject| rejected' || true"
)
CMD_LOG_BOUNCE = (
    "journalctl -u postfix --since today --no-pager 2>/dev/null "
    "| grep -ciE ' bounce| bounced' || true"
)
CMD_LOG_AMAVIS = (
    "journalctl -u postfix --since today --no-pager 2>/dev/null "
    "| grep -ci amavis || true"
)
CMD_LOG_SPAM = (
    "journalctl -u postfix --since today --no-pager 2>/dev/null "
    "| grep -ciE ' spam| spamd' || true"
)
CMD_FAIL2BAN = "fail2ban-client status 2>/dev/null | grep -i 'Currently banned' || true"
CMD_RECENT_LOG = (
    "journalctl -u postfix --since today -n 30 --no-pager 2>/dev/null "
    "|| tail -30 /var/log/mail.log 2>/dev/null "
    "|| tail -30 /var/log/maillog 2>/dev/null"
)

_ALLOWED = frozenset(
    {
        CMD_MAILQ,
        CMD_POSTFIX,
        CMD_DOVECOT,
        CMD_OPENDKIM,
        CMD_AMAVIS,
        CMD_CLAMAV,
        CMD_PFLOGSUMM,
        CMD_QUEUE_DIRS,
        CMD_LOG_REJECT,
        CMD_LOG_BOUNCE,
        CMD_LOG_AMAVIS,
        CMD_LOG_SPAM,
        CMD_FAIL2BAN,
        CMD_RECENT_LOG,
    }
)


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


def _parse_int(out: str) -> int | None:
    out = out.strip()
    if not out.isdigit():
        return None
    return int(out)


def _parse_queue_dirs(text: str) -> tuple[int | None, int | None, int | None]:
    active = deferred = hold = None
    for part in text.split():
        if part.startswith("active="):
            active = _parse_int(part.split("=", 1)[1])
        elif part.startswith("deferred="):
            deferred = _parse_int(part.split("=", 1)[1])
        elif part.startswith("hold="):
            hold = _parse_int(part.split("=", 1)[1])
    return active, deferred, hold


def _parse_fail2ban_banned(text: str) -> int | None:
    m = re.search(r"Currently banned:\s*(\d+)", text, re.I)
    return int(m.group(1)) if m else None


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
    queue_active: int | None
    queue_deferred: int | None
    queue_hold: int | None
    postfix_active: bool | None
    dovecot_active: bool | None
    opendkim_active: bool | None
    amavis_active: bool | None
    clamav_active: bool | None
    mail_received: int | None
    mail_delivered: int | None
    mail_bounced: int | None
    mail_rejected: int | None
    mail_deferred: int | None
    log_reject_lines: int | None
    log_bounce_lines: int | None
    log_amavis_lines: int | None
    log_spam_lines: int | None
    fail2ban_banned: int | None
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
            amavis_active = clamav_active = None
            for cmd, name in (
                (CMD_POSTFIX, "postfix"),
                (CMD_DOVECOT, "dovecot"),
                (CMD_OPENDKIM, "opendkim"),
                (CMD_AMAVIS, "amavis"),
                (CMD_CLAMAV, "clamav"),
            ):
                code, out, err = _run(client, cmd)
                active = _service_active(out) if code == 0 else None
                if name == "postfix":
                    postfix_active = active
                elif name == "dovecot":
                    dovecot_active = active
                elif name == "opendkim":
                    opendkim_active = active
                elif name == "amavis":
                    amavis_active = active
                else:
                    clamav_active = active

            queue_messages, queue_kb = None, None
            code, out, err = _run(client, CMD_MAILQ)
            if code == 0:
                queue_messages, queue_kb = _parse_mailq(out)
            else:
                errors.append(f"mailq: {err or out}")

            queue_active = queue_deferred = queue_hold = None
            code, out, err = _run(client, CMD_QUEUE_DIRS)
            if code == 0 and out:
                queue_active, queue_deferred, queue_hold = _parse_queue_dirs(out)

            stats_source = None
            mail_received = mail_delivered = mail_bounced = mail_rejected = mail_deferred = None
            code, out, err = _run(client, CMD_PFLOGSUMM)
            if code == 0 and out:
                parsed = parse_pflogsumm(out)
                if parsed:
                    stats_source = "pflogsumm"
                    mail_received = parsed.get("mail_received")
                    mail_delivered = parsed.get("mail_delivered")
                    mail_bounced = parsed.get("mail_bounced")
                    mail_rejected = parsed.get("mail_rejected")
                    mail_deferred = parsed.get("mail_deferred")

            log_reject = log_bounce = log_amavis = log_spam = None
            for cmd, assign in (
                (CMD_LOG_REJECT, "reject"),
                (CMD_LOG_BOUNCE, "bounce"),
                (CMD_LOG_AMAVIS, "amavis"),
                (CMD_LOG_SPAM, "spam"),
            ):
                code, out, err = _run(client, cmd)
                val = _parse_int(out) if code == 0 and out.strip().isdigit() else None
                if assign == "reject":
                    log_reject = val
                elif assign == "bounce":
                    log_bounce = val
                elif assign == "amavis":
                    log_amavis = val
                else:
                    log_spam = val

            fail2ban_banned = None
            code, out, err = _run(client, CMD_FAIL2BAN)
            if code == 0 and out:
                fail2ban_banned = _parse_fail2ban_banned(out)

            recent: str | None = None
            code, out, err = _run(client, CMD_RECENT_LOG)
            if code == 0 and out:
                recent = out[:4000]

            return EmailSshInsights(
                collected_at=now,
                queue_messages=queue_messages,
                queue_size_kb=queue_kb,
                queue_active=queue_active,
                queue_deferred=queue_deferred,
                queue_hold=queue_hold,
                postfix_active=postfix_active,
                dovecot_active=dovecot_active,
                opendkim_active=opendkim_active,
                amavis_active=amavis_active,
                clamav_active=clamav_active,
                mail_received=mail_received,
                mail_delivered=mail_delivered,
                mail_bounced=mail_bounced,
                mail_rejected=mail_rejected,
                mail_deferred=mail_deferred,
                log_reject_lines=log_reject,
                log_bounce_lines=log_bounce,
                log_amavis_lines=log_amavis,
                log_spam_lines=log_spam,
                fail2ban_banned=fail2ban_banned,
                stats_source=stats_source,
                recent_log_sample=recent,
                error="; ".join(errors) if errors else None,
            )
    except CredentialError as exc:
        return EmailSshInsights(
            collected_at=now,
            queue_messages=None,
            queue_size_kb=None,
            queue_active=None,
            queue_deferred=None,
            queue_hold=None,
            postfix_active=None,
            dovecot_active=None,
            opendkim_active=None,
            amavis_active=None,
            clamav_active=None,
            mail_received=None,
            mail_delivered=None,
            mail_bounced=None,
            mail_rejected=None,
            mail_deferred=None,
            log_reject_lines=None,
            log_bounce_lines=None,
            log_amavis_lines=None,
            log_spam_lines=None,
            fail2ban_banned=None,
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
