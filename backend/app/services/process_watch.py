from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.process_watch import ProcessWatch
from app.monitoring.process_check import fetch_process_listing, process_in_listing, valid_process_name
from app.schemas.process_watch import ProcessWatchCreate, ProcessWatchRead, ProcessWatchUpdate
from app.services.process_mail import MailNotConfigured, send_process_down_mail

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProcessWatchError(Exception):
    pass


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_recipients(raw: list[str]) -> list[str]:
    found: list[str] = []
    for item in raw:
        for part in re.split(r"[,;\s]+", item.strip()):
            address = part.strip().lower()
            if not address:
                continue
            if not EMAIL_RE.fullmatch(address):
                raise ProcessWatchError(f"Invalid email: {part.strip()}")
            if address not in found:
                found.append(address)
    if not found:
        raise ProcessWatchError("At least one email is required")
    if len(found) > 20:
        raise ProcessWatchError("At most 20 emails")
    return found


def validate_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as exc:
        raise ProcessWatchError("IP address is invalid") from exc


def recipient_list(stored: str) -> list[str]:
    return [part for part in stored.split(",") if part]


def validate_label(value: str) -> str:
    label = value.strip()
    if not label or len(label) > 128 or any(ord(ch) < 32 for ch in label):
        raise ProcessWatchError("Label is required")
    return label


def validate_description(value: str) -> str:
    text = value.strip()
    if len(text) > 2000 or any(ord(ch) < 32 and ch not in "\n\r\t" for ch in text):
        raise ProcessWatchError("Description is too long")
    return text


def validate_check_interval(amount: int, unit: str) -> None:
    if unit == "seconds":
        if amount < 15 or amount > 86400:
            raise ProcessWatchError("Check interval must be at least 15 seconds")
        return
    if unit == "minutes":
        if amount < 1 or amount > 10080:
            raise ProcessWatchError("Check interval in minutes must be from 1 to 10080")
        return
    raise ProcessWatchError("Check interval unit must be seconds or minutes")


def _check_delta(row: ProcessWatch) -> timedelta:
    if row.check_interval_unit == "minutes":
        return timedelta(minutes=row.check_interval)
    return timedelta(seconds=row.check_interval)


def check_is_due(row: ProcessWatch, now: datetime) -> bool:
    last = _aware(row.last_checked_at)
    if last is None:
        return True
    return now - last >= _check_delta(row)


def to_read(row: ProcessWatch) -> ProcessWatchRead:
    return ProcessWatchRead(
        id=row.id,
        ip_address=row.ip_address,
        ssh_port=row.ssh_port,
        ssh_username=row.ssh_username,
        label=row.label or "",
        description=row.description or "",
        process_name=row.process_name,
        recipients=recipient_list(row.recipients),
        check_interval=row.check_interval,
        check_interval_unit=row.check_interval_unit,
        mail_interval_minutes=row.mail_interval_minutes,
        enabled=row.enabled,
        status=row.status,
        last_checked_at=row.last_checked_at,
        down_since=row.down_since,
        resolved_at=row.resolved_at,
        last_emailed_at=row.last_emailed_at,
        mail_sent=row.mail_sent,
        mail_error=row.mail_error,
        last_error=row.last_error,
        created_at=row.created_at,
    )


def create_process_watch(db: Session, payload: ProcessWatchCreate) -> ProcessWatch:
    name = payload.process_name.strip()
    if not valid_process_name(name):
        raise ProcessWatchError("Process name must use letters, numbers, and ._/: - only")
    username = payload.ssh_username.strip()
    if not username or any(ch.isspace() for ch in username):
        raise ProcessWatchError("Username is invalid")
    recipients = parse_recipients(payload.recipients)
    validate_check_interval(payload.check_interval, payload.check_interval_unit)
    row = ProcessWatch(
        ip_address=validate_ip(payload.ip_address),
        ssh_port=payload.ssh_port,
        ssh_username=username,
        ssh_password=payload.ssh_password,
        label=validate_label(payload.label),
        description=validate_description(payload.description),
        process_name=name,
        recipients=",".join(recipients),
        check_interval=payload.check_interval,
        check_interval_unit=payload.check_interval_unit,
        mail_interval_minutes=payload.mail_interval_minutes,
        enabled=payload.enabled,
        status="unknown",
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_process_watch(db: Session, row: ProcessWatch, payload: ProcessWatchUpdate) -> ProcessWatch:
    name = payload.process_name.strip()
    if not valid_process_name(name):
        raise ProcessWatchError("Process name must use letters, numbers, and ._/: - only")
    username = payload.ssh_username.strip()
    if not username or any(ch.isspace() for ch in username):
        raise ProcessWatchError("Username is invalid")
    validate_check_interval(payload.check_interval, payload.check_interval_unit)
    row.ip_address = validate_ip(payload.ip_address)
    row.ssh_port = payload.ssh_port
    row.ssh_username = username
    row.label = validate_label(payload.label)
    row.description = validate_description(payload.description)
    row.process_name = name
    row.recipients = ",".join(parse_recipients(payload.recipients))
    row.check_interval = payload.check_interval
    row.check_interval_unit = payload.check_interval_unit
    row.mail_interval_minutes = payload.mail_interval_minutes
    row.enabled = payload.enabled
    password = payload.ssh_password.strip()
    if password:
        row.ssh_password = password
    db.commit()
    db.refresh(row)
    return row


def list_process_watches(db: Session) -> list[ProcessWatch]:
    return db.query(ProcessWatch).order_by(ProcessWatch.id.desc()).all()


def get_process_watch(db: Session, watch_id: int) -> ProcessWatch | None:
    return db.query(ProcessWatch).filter(ProcessWatch.id == watch_id).one_or_none()


def delete_process_watch(db: Session, row: ProcessWatch) -> None:
    db.delete(row)
    db.commit()


def _mail_due(row: ProcessWatch, now: datetime, *, newly_down: bool) -> bool:
    if newly_down:
        return True
    last = _aware(row.last_emailed_at)
    if last is None:
        return True
    return now - last >= timedelta(minutes=row.mail_interval_minutes)


def _send_down_mail(row: ProcessWatch, now: datetime, send: Callable[..., None]) -> None:
    down_since = _aware(row.down_since) or now
    try:
        send(
            ip_address=row.ip_address,
            process_name=row.process_name,
            recipients=recipient_list(row.recipients),
            down_since=down_since.isoformat(),
        )
    except MailNotConfigured:
        row.last_emailed_at = now
        row.mail_sent = False
        row.mail_error = "Mail was not sent. SMTP is not configured."
        return
    except Exception as exc:
        row.last_emailed_at = now
        row.mail_sent = False
        row.mail_error = f"Mail was not sent. {exc}"[:500]
        return
    row.last_emailed_at = now
    row.mail_sent = True
    row.mail_error = None


def check_watch(
    db: Session,
    row: ProcessWatch,
    *,
    now: datetime | None = None,
    fetch: Callable[..., str] | None = None,
    send: Callable[..., None] | None = None,
) -> ProcessWatch:
    now = now or datetime.now(timezone.utc)
    if not row.enabled:
        return row
    fetch_fn = fetch or _fetch_listing
    send_fn = send or send_process_down_mail
    row.last_checked_at = now
    try:
        listing = fetch_fn(row)
    except Exception as exc:
        row.last_error = (str(exc) or "SSH failed")[:2000]
        db.commit()
        db.refresh(row)
        return row

    row.last_error = None
    if process_in_listing(listing, row.process_name):
        if row.status == "down":
            row.resolved_at = now
        row.status = "up"
        db.commit()
        db.refresh(row)
        return row

    newly_down = row.status != "down"
    if newly_down:
        row.down_since = now
        row.resolved_at = None
    row.status = "down"
    if _mail_due(row, now, newly_down=newly_down):
        _send_down_mail(row, now, send_fn)
    db.commit()
    db.refresh(row)
    return row


def _fetch_listing(row: ProcessWatch) -> str:
    return fetch_process_listing(
        host=row.ip_address,
        port=row.ssh_port,
        username=row.ssh_username,
        ssh_password=row.ssh_password,
    )


def check_enabled_watches(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    rows = db.query(ProcessWatch).filter(ProcessWatch.enabled.is_(True)).order_by(ProcessWatch.id).all()
    checked = 0
    down = 0
    mailed = 0
    failed = 0
    for row in rows:
        if not check_is_due(row, now):
            continue
        mailed_at = row.last_emailed_at
        try:
            check_watch(db, row, now=now)
        except Exception:
            failed += 1
            continue
        checked += 1
        if row.last_error:
            failed += 1
        if row.status == "down":
            down += 1
        if row.mail_sent and row.last_emailed_at != mailed_at:
            mailed += 1
    return {"checked": checked, "down": down, "mailed": mailed, "failed": failed}
