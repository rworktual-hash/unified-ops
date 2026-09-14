from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.email_mgmt_session import get_email_mgmt_engine
from app.models.email_log_event import EmailLogEvent
from app.models.email_sync_state import EmailSyncState
from app.models.server import Server

STREAM_KEY = "email_mgmt_events"


def _parse_remote_time(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if value is None:
        return datetime.now(timezone.utc)
    text_val = str(value).strip()
    if text_val.endswith("Z"):
        text_val = text_val[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)


def _resolve_server_id(db: Session, host_value: str | None) -> int | None:
    if host_value:
        host_value = host_value.strip()
        name = settings.email_mgmt_host_map.get(host_value)
        if name:
            row = db.query(Server).filter(Server.server_name == name).first()
            if row:
                return row.id
        row = db.query(Server).filter(Server.ip_address == host_value).first()
        if row:
            return row.id
    default_name = settings.email_mgmt_default_server_name
    row = db.query(Server).filter(Server.server_name == default_name).first()
    return row.id if row else None


def _get_or_create_state(db: Session) -> EmailSyncState:
    state = db.query(EmailSyncState).filter(EmailSyncState.stream_key == STREAM_KEY).first()
    if state is None:
        state = EmailSyncState(stream_key=STREAM_KEY, last_source_id=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def sync_email_events_from_mgmt_db(db: Session) -> dict:
    engine = get_email_mgmt_engine()
    if engine is None:
        return {"ok": False, "skipped": True, "reason": "EMAIL_MGMT_DATABASE_URL not set"}

    state = _get_or_create_state(db)
    cfg = settings
    cols = [
        cfg.email_mgmt_col_id,
        cfg.email_mgmt_col_time,
        cfg.email_mgmt_col_event,
        cfg.email_mgmt_col_direction,
        cfg.email_mgmt_col_from,
        cfg.email_mgmt_col_to,
        cfg.email_mgmt_col_subject,
        cfg.email_mgmt_col_status,
        cfg.email_mgmt_col_dsn,
        cfg.email_mgmt_col_queue_id,
    ]
    if cfg.email_mgmt_col_host:
        cols.append(cfg.email_mgmt_col_host)

    col_list = ", ".join(f"`{c}`" for c in cols)
    table = cfg.email_mgmt_events_table
    id_col = cfg.email_mgmt_col_id
    sql = text(
        f"SELECT {col_list} FROM `{table}` WHERE `{id_col}` > :last_id "
        f"ORDER BY `{id_col}` ASC LIMIT :lim"
    )

    inserted = 0
    now = datetime.now(timezone.utc)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sql,
                {"last_id": state.last_source_id, "lim": cfg.email_mgmt_sync_batch_size},
            ).mappings().all()

        max_id = state.last_source_id
        for row in rows:
            source_id = int(row[cfg.email_mgmt_col_id])
            max_id = max(max_id, source_id)
            exists = db.query(EmailLogEvent.id).filter(EmailLogEvent.source_id == source_id).first()
            if exists:
                continue
            host_val = row.get(cfg.email_mgmt_col_host) if cfg.email_mgmt_col_host else None
            server_id = _resolve_server_id(db, str(host_val) if host_val is not None else None)
            event = EmailLogEvent(
                source_id=source_id,
                server_id=server_id,
                occurred_at=_parse_remote_time(row.get(cfg.email_mgmt_col_time)),
                event_type=_str(row.get(cfg.email_mgmt_col_event)),
                direction=_str(row.get(cfg.email_mgmt_col_direction)),
                from_addr=_str(row.get(cfg.email_mgmt_col_from)),
                to_addr=_str(row.get(cfg.email_mgmt_col_to)),
                subject=_str(row.get(cfg.email_mgmt_col_subject)),
                status=_str(row.get(cfg.email_mgmt_col_status)),
                dsn=_str(row.get(cfg.email_mgmt_col_dsn)),
                queue_id=_str(row.get(cfg.email_mgmt_col_queue_id)),
                synced_at=now,
            )
            db.add(event)
            inserted += 1

        state.last_source_id = max_id
        state.last_synced_at = now
        state.last_error = None
        db.commit()
        return {"ok": True, "inserted": inserted, "last_source_id": max_id}
    except Exception as exc:
        db.rollback()
        state.last_error = str(exc)[:500]
        db.commit()
        return {"ok": False, "error": str(exc), "inserted": inserted}


def _str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def compute_email_overview(db: Session, *, hours: int = 24) -> dict:
    """Aggregate synced events for dashboard cards (Unified Ops copy)."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    events = (
        db.query(EmailLogEvent)
        .filter(EmailLogEvent.occurred_at >= since)
        .all()
    )
    total = len(events)
    inbound = sum(1 for e in events if (e.direction or "").lower().startswith("in"))
    outbound = sum(1 for e in events if (e.direction or "").lower().startswith("out"))
    delivered = sum(1 for e in events if (e.status or "").lower() in {"delivered", "sent"})
    bounced = sum(1 for e in events if "bounce" in (e.status or "").lower())
    failed = sum(1 for e in events if (e.status or "").lower() in {"failed", "reject", "rejected"})
    return {
        "period_hours": hours,
        "total": total,
        "inbound": inbound,
        "outbound": outbound,
        "delivered": delivered,
        "bounced": bounced,
        "failed": failed,
    }
