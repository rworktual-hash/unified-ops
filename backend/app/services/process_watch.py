from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.process_watch import ProcessMailDefault, ProcessWatch, ProcessWatchChange, ProcessWatchMail
from app.monitoring.process_check import (
    ProcessCheckError,
    fetch_exact_pid,
    fetch_process_listing,
    fetch_service_port,
    format_pids,
    matching_pids,
    probe_ssh_login,
    valid_process_name,
)
from app.schemas.process_watch import (
    ProcessMailDefaults,
    ProcessMailEntry,
    ProcessWatchChangeRead,
    ProcessWatchCreate,
    ProcessWatchMailRead,
    ProcessWatchRead,
    ProcessWatchUpdate,
)
from app.services.process_mail import MailNotConfigured, send_process_down_mail, send_process_up_mail

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProcessWatchError(Exception):
    pass


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_recipients(raw: list[str], *, required: bool = True) -> list[str]:
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
    if required and not found:
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


def to_read(row: ProcessWatch, *, server_now: datetime | None = None) -> ProcessWatchRead:
    return ProcessWatchRead(
        id=row.id,
        ip_address=row.ip_address,
        ssh_port=row.ssh_port,
        ssh_username=row.ssh_username,
        label=row.label or "",
        description=row.description or "",
        process_name=row.process_name,
        pid=row.pid or "",
        service_port=row.service_port or "",
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
        server_now=server_now or datetime.now(timezone.utc),
    )


def create_process_watch(db: Session, payload: ProcessWatchCreate, *, verify_ssh: bool = False) -> ProcessWatch:
    name = payload.process_name.strip()
    if not valid_process_name(name):
        raise ProcessWatchError("Process name must use letters, numbers, and ._/: - only")
    username = payload.ssh_username.strip()
    if not username or any(ch.isspace() for ch in username):
        raise ProcessWatchError("Username is invalid")
    recipients = parse_recipients(payload.recipients, required=False)
    _reject_if_in_defaults(db, recipients)
    validate_check_interval(payload.check_interval, payload.check_interval_unit)
    ip_address = validate_ip(payload.ip_address)
    _ensure_unique_endpoint(db, ip_address, payload.ssh_port, name)
    if verify_ssh:
        try:
            probe_ssh_login(
                host=ip_address,
                port=payload.ssh_port,
                username=username,
                ssh_password=payload.ssh_password,
            )
        except ProcessCheckError as exc:
            raise ProcessWatchError(str(exc) or "SSH login failed") from exc
    row = ProcessWatch(
        ip_address=ip_address,
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
    db.flush()
    _add_change(db, watch_id=row.id, label=row.label, summary="Added this service.")
    db.commit()
    db.refresh(row)
    if verify_ssh:
        return check_watch(db, row, force=True)
    return row


def update_process_watch(db: Session, row: ProcessWatch, payload: ProcessWatchUpdate) -> ProcessWatch:
    name = payload.process_name.strip()
    if not valid_process_name(name):
        raise ProcessWatchError("Process name must use letters, numbers, and ._/: - only")
    username = payload.ssh_username.strip()
    if not username or any(ch.isspace() for ch in username):
        raise ProcessWatchError("Username is invalid")
    recipients = parse_recipients(payload.recipients, required=False)
    _reject_if_in_defaults(db, recipients)
    validate_check_interval(payload.check_interval, payload.check_interval_unit)
    ip_address = validate_ip(payload.ip_address)
    _ensure_unique_endpoint(db, ip_address, payload.ssh_port, name, exclude_id=row.id)
    label = validate_label(payload.label)
    description = validate_description(payload.description)
    password = payload.ssh_password.strip()
    summary = _edit_summary(
        row,
        label=label,
        description=description,
        process_name=name,
        ip_address=ip_address,
        ssh_port=payload.ssh_port,
        ssh_username=username,
        recipients=recipients,
        check_interval=payload.check_interval,
        check_interval_unit=payload.check_interval_unit,
        mail_interval_minutes=payload.mail_interval_minutes,
        enabled=payload.enabled,
        password_changed=bool(password),
    )
    row.ip_address = ip_address
    row.ssh_port = payload.ssh_port
    row.ssh_username = username
    row.label = label
    row.description = description
    row.process_name = name
    row.recipients = ",".join(recipients)
    row.check_interval = payload.check_interval
    row.check_interval_unit = payload.check_interval_unit
    row.mail_interval_minutes = payload.mail_interval_minutes
    row.enabled = payload.enabled
    if not payload.enabled:
        row.status = "unknown"
        row.pid = ""
        row.service_port = ""
        row.last_error = None
    if password:
        row.ssh_password = password
    if summary:
        _add_change(db, watch_id=row.id, label=row.label, summary=summary)
    db.commit()
    db.refresh(row)
    return row


def list_process_watches(db: Session) -> list[ProcessWatch]:
    return db.query(ProcessWatch).order_by(ProcessWatch.id.desc()).all()


def get_process_watch(db: Session, watch_id: int) -> ProcessWatch | None:
    return db.query(ProcessWatch).filter(ProcessWatch.id == watch_id).one_or_none()


def delete_process_watch(db: Session, row: ProcessWatch) -> None:
    _add_change(db, watch_id=row.id, label=row.label, summary="Deleted this service.")
    db.delete(row)
    db.commit()


def _add_change(db: Session, *, watch_id: int | None, label: str, summary: str) -> None:
    db.add(
        ProcessWatchChange(
            watch_id=watch_id,
            label=(label or "").strip()[:128],
            summary=summary[:2000],
            created_at=datetime.now(timezone.utc),
        )
    )


def _edit_summary(
    row: ProcessWatch,
    *,
    label: str,
    description: str,
    process_name: str,
    ip_address: str,
    ssh_port: int,
    ssh_username: str,
    recipients: list[str],
    check_interval: int,
    check_interval_unit: str,
    mail_interval_minutes: int,
    enabled: bool,
    password_changed: bool,
) -> str:
    lines: list[str] = []

    def add(title: str, old: object, new: object) -> None:
        if str(old) != str(new):
            lines.append(f"{title}: {old} → {new}")

    add("Label", row.label, label)
    add("Description", row.description, description)
    add("Process name", row.process_name, process_name)
    add("Server", row.ip_address, ip_address)
    add("SSH port", row.ssh_port, ssh_port)
    add("Username", row.ssh_username, ssh_username)
    add("Additional mail ids", row.recipients or "—", ",".join(recipients) or "—")
    add(
        "Check every",
        f"{row.check_interval} {row.check_interval_unit}",
        f"{check_interval} {check_interval_unit}",
    )
    add("Mail every", f"{row.mail_interval_minutes} minutes", f"{mail_interval_minutes} minutes")
    add("Active", "Active" if row.enabled else "Inactive", "Active" if enabled else "Inactive")
    if password_changed:
        lines.append("Password: updated")
    return "\n".join(lines)


def _add_mail_history(db: Session, row: ProcessWatch, *, kind: str, mailed_at: datetime) -> None:
    db.add(
        ProcessWatchMail(
            watch_id=row.id,
            label=(row.label or row.process_name or "").strip()[:128],
            ip_address=row.ip_address,
            process_name=row.process_name,
            kind=kind,
            mailed_at=mailed_at,
        )
    )


def list_process_watch_mail(db: Session, *, limit: int = 80) -> list[ProcessWatchMail]:
    return db.query(ProcessWatchMail).order_by(ProcessWatchMail.id.desc()).limit(limit).all()


def to_mail(row: ProcessWatchMail) -> ProcessWatchMailRead:
    return ProcessWatchMailRead.model_validate(row)


def list_process_watch_changes(db: Session, *, limit: int = 40) -> list[ProcessWatchChange]:
    return db.query(ProcessWatchChange).order_by(ProcessWatchChange.id.desc()).limit(limit).all()


def to_change(row: ProcessWatchChange) -> ProcessWatchChangeRead:
    return ProcessWatchChangeRead.model_validate(row)


def _reject_if_in_defaults(db: Session, recipients: list[str]) -> None:
    defaults = set(get_default_recipients(db))
    overlap = [address for address in recipients if address in defaults]
    if not overlap:
        return
    listed = ", ".join(overlap)
    verb = "is" if len(overlap) == 1 else "are"
    raise ProcessWatchError(
        f"{listed} {verb} already in the default mail ids. Remove from additional mail ids."
    )


def validate_team(value: str) -> str:
    team = value.strip()
    if len(team) > 64 or any(ord(ch) < 32 for ch in team):
        raise ProcessWatchError("Team name is too long")
    return team


def _default_pairs(payload: ProcessMailDefaults) -> list[tuple[str, str]]:
    if payload.entries:
        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for entry in payload.entries:
            addresses = parse_recipients([entry.email], required=True)
            if len(addresses) != 1:
                raise ProcessWatchError("Enter one email on each row")
            address = addresses[0]
            if address in seen:
                raise ProcessWatchError(f"{address} is already in the default mail ids")
            seen.add(address)
            pairs.append((address, validate_team(entry.team)))
        if len(pairs) > 20:
            raise ProcessWatchError("At most 20 emails")
        return pairs
    return [(address, "") for address in parse_recipients(payload.recipients, required=False)]


def get_default_entries(db: Session) -> list[ProcessMailEntry]:
    row = db.get(ProcessMailDefault, 1)
    if row is None:
        return []
    emails = recipient_list(row.recipients)
    try:
        stored = json.loads(row.teams) if row.teams else []
    except json.JSONDecodeError:
        stored = []
    teams = [str(item) for item in stored] if isinstance(stored, list) else []
    return [
        ProcessMailEntry(email=email, team=teams[index] if index < len(teams) else "")
        for index, email in enumerate(emails)
    ]


def get_default_recipients(db: Session) -> list[str]:
    return [entry.email for entry in get_default_entries(db)]


def set_default_recipients(db: Session, payload: ProcessMailDefaults) -> list[str]:
    pairs = _default_pairs(payload)
    addresses = [email for email, _team in pairs]
    row = db.get(ProcessMailDefault, 1)
    if row is None:
        row = ProcessMailDefault(id=1, recipients="", teams="")
        db.add(row)
    row.recipients = ",".join(addresses)
    row.teams = json.dumps([team for _email, team in pairs])
    db.commit()
    return addresses


def combined_recipients(db: Session, row: ProcessWatch) -> list[str]:
    found: list[str] = []
    for address in get_default_recipients(db) + recipient_list(row.recipients):
        if address not in found:
            found.append(address)
    return found


def _send_down_mail(db: Session, row: ProcessWatch, now: datetime, send: Callable[..., None]) -> None:
    down_since = _aware(row.down_since) or now
    recipients = combined_recipients(db, row)
    if not recipients:
        row.last_emailed_at = now
        row.mail_sent = False
        row.mail_error = "Mail was not sent. Add a default or additional mail id."
        return
    try:
        send(
            ip_address=row.ip_address,
            label=row.label,
            process_name=row.process_name,
            recipients=recipients,
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


def _send_up_mail(db: Session, row: ProcessWatch, now: datetime, send: Callable[..., None]) -> None:
    recipients = combined_recipients(db, row)
    if not recipients:
        row.last_emailed_at = now
        row.mail_sent = False
        row.mail_error = "Mail was not sent. Add a default or additional mail id."
        return
    try:
        send(
            ip_address=row.ip_address,
            label=row.label,
            process_name=row.process_name,
            recipients=recipients,
            restored_at=now.isoformat(),
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
    force: bool = False,
) -> ProcessWatch:
    now = now or datetime.now(timezone.utc)
    if not row.enabled:
        return row
    if not force:
        db.refresh(row)
        if not row.enabled or not check_is_due(row, now):
            return row
    send_down = send or send_process_down_mail
    send_up = send or send_process_up_mail
    row.last_checked_at = now
    try:
        pids = _resolve_pids(row, fetch)
    except Exception as exc:
        row.last_error = (str(exc) or "SSH failed")[:2000]
        db.commit()
        db.refresh(row)
        return row

    row.last_error = None
    watch_id = row.id
    if pids:
        pid_text = format_pids(pids)
        port_text = "" if fetch is not None else _service_port(row, pid_text.split(",")[0].strip())
        db.expire(row)
        claimed = (
            db.query(ProcessWatch)
            .filter(ProcessWatch.id == watch_id, ProcessWatch.status == "down")
            .update(
                {
                    ProcessWatch.status: "up",
                    ProcessWatch.resolved_at: now,
                    ProcessWatch.pid: pid_text,
                    ProcessWatch.service_port: port_text,
                    ProcessWatch.last_error: None,
                    ProcessWatch.last_checked_at: now,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        row = db.get(ProcessWatch, watch_id)
        if claimed:
            _send_up_mail(db, row, now, send_up)
            if row.mail_sent:
                _add_mail_history(db, row, kind="up", mailed_at=now)
        else:
            row.status = "up"
            row.pid = pid_text
            row.service_port = port_text
            row.last_error = None
            row.last_checked_at = now
        db.commit()
        db.refresh(row)
        return row

    db.expire(row)
    current = db.get(ProcessWatch, watch_id)
    cutoff = now - timedelta(minutes=current.mail_interval_minutes)
    down_values = {
        ProcessWatch.pid: "",
        ProcessWatch.service_port: "",
        ProcessWatch.last_error: None,
        ProcessWatch.last_checked_at: now,
        ProcessWatch.last_emailed_at: now,
    }
    first_down = (
        db.query(ProcessWatch)
        .filter(ProcessWatch.id == watch_id, ProcessWatch.status != "down")
        .update(
            {
                **down_values,
                ProcessWatch.status: "down",
                ProcessWatch.down_since: now,
                ProcessWatch.resolved_at: None,
            },
            synchronize_session=False,
        )
    )
    repeat = 0
    if not first_down:
        repeat = (
            db.query(ProcessWatch)
            .filter(
                ProcessWatch.id == watch_id,
                ProcessWatch.status == "down",
                or_(ProcessWatch.last_emailed_at.is_(None), ProcessWatch.last_emailed_at <= cutoff),
            )
            .update(down_values, synchronize_session=False)
        )
    db.commit()
    row = db.get(ProcessWatch, watch_id)
    if first_down or repeat:
        _send_down_mail(db, row, now, send_down)
        if first_down and row.mail_sent:
            _add_mail_history(db, row, kind="down", mailed_at=now)
    else:
        row.status = "down"
        row.pid = ""
        row.service_port = ""
        row.last_error = None
        row.last_checked_at = now
    db.commit()
    db.refresh(row)
    return row


def _ensure_unique_endpoint(
    db: Session,
    ip_address: str,
    ssh_port: int,
    process_name: str,
    exclude_id: int | None = None,
) -> None:
    query = db.query(ProcessWatch).filter(
        ProcessWatch.ip_address == ip_address,
        ProcessWatch.ssh_port == ssh_port,
        ProcessWatch.process_name == process_name,
    )
    if exclude_id is not None:
        query = query.filter(ProcessWatch.id != exclude_id)
    if query.first() is not None:
        raise ProcessWatchError("A watch already exists for this process on this IP and port")


def _service_port(row: ProcessWatch, pid: str) -> str:
    return fetch_service_port(
        host=row.ip_address,
        port=row.ssh_port,
        username=row.ssh_username,
        ssh_password=row.ssh_password,
        pid=pid,
    )


def _exact_pid(row: ProcessWatch) -> tuple[str, str]:
    return fetch_exact_pid(
        host=row.ip_address,
        port=row.ssh_port,
        username=row.ssh_username,
        ssh_password=row.ssh_password,
        process_name=row.process_name,
    )


def _resolve_pids(row: ProcessWatch, fetch: Callable[..., str] | None) -> list[str]:
    if fetch is not None:
        return matching_pids(fetch(row), row.process_name)
    kind, pid = _exact_pid(row)
    if kind == "pid":
        return [pid]
    if kind == "down":
        return []
    return matching_pids(_fetch_listing(row), row.process_name)


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
