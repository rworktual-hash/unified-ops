"""Read-only Campaign extras from MariaDB `worktual_email_campaign` (EMAIL_MGMT_*).

Live SELECT like VoiceMG extras — not the incremental email_log_events sync.
Never selects password / secret / token / hash columns.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.db.email_mgmt_session import get_email_mgmt_engine
from app.services.live_cache import get_cached, set_cached

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_HINTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "ssh_pass",
    "hash",
    "webhook",
)

LOG_TABLE = "email_log_realtime"
STATUS_TABLE = "mail_status"
QUEUE_TABLE = "postfix_queue_snapshot"
QUARANTINE_TABLE = "email_quarantine"
CAMPAIGN_QUEUE_TABLE = "email_campaign_queue"

LOG_COLS = (
    "id",
    "log_datetime",
    "event_type",
    "queue_id",
    "message_id",
    "mail_from",
    "mail_to",
    "subject",
    "direction",
    "status",
    "dsn",
    "reason",
    "spam_score",
    "dkim_result",
    "spf_result",
    "classification",
    "server",
    "server_name",
)
QUEUE_COLS = (
    "id",
    "server",
    "server_name",
    "snapshot_at",
    "queue_count",
    "deferred_count",
    "active_count",
    "incoming_count",
    "top_senders",
)
MAIL_STATUS_KEYS = ("sent", "bounce", "deferred", "host_not_reachable")
# Campaign DB uses these labels, not the public gateway IPs.
HOST_ALIASES = {
    "campaign": "email-mgmt-1",
    "mail.worktual.pl": "email-mgmt-1",
}


def _empty(reason: str, *, hours: int = 24, database: str | None = None) -> dict:
    return {
        "ok": False,
        "reason": reason,
        "database": database,
        "period_hours": hours,
        "totals": _empty_totals(),
        "queue": _empty_queue(),
        "servers": [],
        "events": [],
    }


def _empty_totals() -> dict:
    return {
        "sent": 0,
        "bounce": 0,
        "deferred": 0,
        "host_not_reachable": 0,
        "delivered": 0,
        "inbound": 0,
        "outbound": 0,
        "failed": 0,
        "blocked": 0,
        "spam": 0,
        "quarantine": 0,
        "campaign_queued": 0,
        "log_total": 0,
    }


def _empty_queue() -> dict:
    return {
        "queue_count": 0,
        "deferred_count": 0,
        "active_count": 0,
        "incoming_count": 0,
        "snapshot_at": None,
    }


def _table_exists(conn, name: str) -> bool:
    if not _IDENT.match(name):
        return False
    count = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl"
        ),
        {"tbl": name},
    ).scalar()
    return bool(count)


def _safe_columns(conn, table: str) -> list[str]:
    if not _IDENT.match(table):
        return []
    rows = conn.execute(
        text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl "
            "ORDER BY ORDINAL_POSITION"
        ),
        {"tbl": table},
    ).all()
    out: list[str] = []
    for (name,) in rows:
        if not isinstance(name, str) or not _IDENT.match(name):
            continue
        lowered = name.lower()
        if any(hint in lowered for hint in _SECRET_HINTS):
            continue
        out.append(name)
    return out


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text_val = str(value).strip()
    return text_val or None


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    text_val = str(value).strip()
    if not text_val:
        return None
    if text_val.endswith("Z"):
        text_val = text_val[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text_val)
    except ValueError:
        return None


def _iso(value: Any) -> str | None:
    dt = _dt(value)
    return dt.isoformat(sep=" ") if dt else _str(value)


def _host_map() -> dict[str, str]:
    mapping = {key.lower(): value for key, value in settings.email_mgmt_host_map.items()}
    for alias, name in HOST_ALIASES.items():
        mapping.setdefault(alias, name)
    return mapping


def inventory_name(server: str | None, server_name: str | None) -> str | None:
    mapping = _host_map()
    for candidate in (server, server_name):
        key = (candidate or "").strip().lower()
        if key and key in mapping:
            return mapping[key]
    return _str(server_name) or _str(server)


def fold_status_counts(rows: list[tuple[str | None, int]]) -> dict[str, int]:
    out = {key: 0 for key in MAIL_STATUS_KEYS}
    for status, count in rows:
        key = (status or "").strip().lower().replace(" ", "_").replace("-", "_")
        n = _int(count) or 0
        if key in out:
            out[key] += n
        elif "bounce" in key:
            out["bounce"] += n
        elif "defer" in key:
            out["deferred"] += n
        elif key in {"sent", "delivered"}:
            out["sent"] += n
        elif "reach" in key:
            out["host_not_reachable"] += n
    return out


def parse_top_senders(raw: Any, limit: int = 5) -> list[dict]:
    if raw is None:
        return []
    data: Any = raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        text_val = raw.strip()
        if not text_val:
            return []
        try:
            data = json.loads(text_val)
        except json.JSONDecodeError:
            items = []
            for part in text_val.split(","):
                if ":" not in part:
                    continue
                sender, count = part.rsplit(":", 1)
                items.append({"sender": sender.strip(), "count": _int(count) or 0})
            return items[:limit]
    if isinstance(data, dict):
        data = [{"sender": key, "count": val} for key, val in data.items()]
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if isinstance(item, dict):
            sender = _str(item.get("sender") or item.get("mail_from") or item.get("from") or item.get("email"))
            count = _int(item.get("count") or item.get("n") or item.get("total"))
            if sender:
                out.append({"sender": sender, "count": count or 0})
        elif isinstance(item, (list, tuple)) and item:
            sender = _str(item[0])
            count = _int(item[1]) if len(item) > 1 else 0
            if sender:
                out.append({"sender": sender, "count": count or 0})
        if len(out) >= limit:
            break
    return out


def map_queue_row(row: dict) -> dict:
    server = _str(row.get("server"))
    server_name = _str(row.get("server_name"))
    return {
        "server": server,
        "server_name": server_name,
        "inventory_name": inventory_name(server, server_name),
        "queue_count": _int(row.get("queue_count")) or 0,
        "deferred_count": _int(row.get("deferred_count")) or 0,
        "active_count": _int(row.get("active_count")) or 0,
        "incoming_count": _int(row.get("incoming_count")) or 0,
        "snapshot_at": _iso(row.get("snapshot_at")),
        "top_senders": parse_top_senders(row.get("top_senders")),
    }


def map_event(row: dict) -> dict:
    server = _str(row.get("server"))
    server_name = _str(row.get("server_name"))
    return {
        "id": _int(row.get("id")) or 0,
        "occurred_at": _iso(row.get("log_datetime")),
        "event_type": _str(row.get("event_type")),
        "direction": _str(row.get("direction")),
        "from_addr": _str(row.get("mail_from")),
        "to_addr": _str(row.get("mail_to")),
        "subject": _str(row.get("subject")),
        "status": _str(row.get("status")),
        "dsn": _str(row.get("dsn")),
        "reason": _str(row.get("reason")),
        "queue_id": _str(row.get("queue_id")),
        "message_id": _str(row.get("message_id")),
        "spam_score": _num(row.get("spam_score")),
        "dkim_result": _str(row.get("dkim_result")),
        "spf_result": _str(row.get("spf_result")),
        "classification": _str(row.get("classification")),
        "server": server,
        "server_name": server_name,
        "inventory_name": inventory_name(server, server_name),
    }


def latest_queue_rows(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        key = _str(row.get("server")) or _str(row.get("server_name")) or str(row.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(map_queue_row(row))
    return out


def sum_queue(servers: list[dict]) -> dict:
    if not servers:
        return _empty_queue()
    latest = max((row.get("snapshot_at") or "" for row in servers), default="")
    return {
        "queue_count": sum(int(row.get("queue_count") or 0) for row in servers),
        "deferred_count": sum(int(row.get("deferred_count") or 0) for row in servers),
        "active_count": sum(int(row.get("active_count") or 0) for row in servers),
        "incoming_count": sum(int(row.get("incoming_count") or 0) for row in servers),
        "snapshot_at": latest or None,
    }


def fetch_email_extras(hours: int = 24) -> dict:
    hours = max(1, min(hours, 24 * 30))
    cached = get_cached(f"email_extras:{hours}")
    if cached is not None:
        return cached
    out = _fetch_email_extras(hours)
    set_cached(f"email_extras:{hours}", out)
    return out


def _fetch_email_extras(hours: int) -> dict:
    if not settings.email_mgmt_database_url:
        return _empty("EMAIL_MGMT_DATABASE_URL not set", hours=hours)
    engine = get_email_mgmt_engine()
    if engine is None:
        return _empty("engine unavailable", hours=hours)

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    totals = _empty_totals()
    servers: list[dict] = []
    events: list[dict] = []
    database: str | None = None
    found = False

    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("SET SESSION max_execution_time = 10000"))
            except Exception:
                pass
            database = _str(conn.execute(text("SELECT DATABASE()")).scalar())

            if _table_exists(conn, QUEUE_TABLE):
                found = True
                cols = [c for c in QUEUE_COLS if c in set(_safe_columns(conn, QUEUE_TABLE))]
                if cols:
                    quoted = ", ".join(f"`{c}`" for c in cols)
                    order = "snapshot_at" if "snapshot_at" in cols else "id"
                    rows = (
                        conn.execute(
                            text(
                                f"SELECT {quoted} FROM `{QUEUE_TABLE}` "
                                f"ORDER BY `{order}` DESC, `id` DESC LIMIT 20"
                            )
                        )
                        .mappings()
                        .all()
                    )
                    servers = latest_queue_rows([dict(row) for row in rows])

            if _table_exists(conn, STATUS_TABLE):
                found = True
                status_cols = set(_safe_columns(conn, STATUS_TABLE))
                if "status" in status_cols:
                    if "log_date" in status_cols:
                        time_expr = (
                            "TIMESTAMP(`log_date`, IFNULL(`log_time`, '00:00:00'))"
                            if "log_time" in status_cols
                            else "`log_date`"
                        )
                        status_rows = conn.execute(
                            text(
                                f"SELECT `status` AS st, COUNT(*) AS n FROM `{STATUS_TABLE}` "
                                f"WHERE {time_expr} >= :since GROUP BY `status`"
                            ),
                            {"since": since},
                        ).all()
                    else:
                        status_rows = conn.execute(
                            text(f"SELECT `status` AS st, COUNT(*) AS n FROM `{STATUS_TABLE}` GROUP BY `status`")
                        ).all()
                    totals.update(fold_status_counts([(row[0], int(row[1] or 0)) for row in status_rows]))

            if _table_exists(conn, LOG_TABLE):
                found = True
                present = set(_safe_columns(conn, LOG_TABLE))
                if "log_datetime" in present:
                    parts = ["COUNT(*) AS log_total"]
                    if "direction" in present:
                        parts.append(
                            "SUM(CASE WHEN LOWER(IFNULL(`direction`,'')) LIKE 'in%' THEN 1 ELSE 0 END) AS inbound"
                        )
                        parts.append(
                            "SUM(CASE WHEN LOWER(IFNULL(`direction`,'')) LIKE 'out%' THEN 1 ELSE 0 END) AS outbound"
                        )
                    if "status" in present:
                        parts.append(
                            "SUM(CASE WHEN LOWER(IFNULL(`status`,'')) IN ('sent','delivered') THEN 1 ELSE 0 END) AS delivered"
                        )
                        parts.append(
                            "SUM(CASE WHEN LOWER(IFNULL(`status`,'')) LIKE '%bounce%' THEN 1 ELSE 0 END) AS bounced"
                        )
                        parts.append(
                            "SUM(CASE WHEN LOWER(IFNULL(`status`,'')) LIKE '%defer%' THEN 1 ELSE 0 END) AS deferred"
                        )
                        parts.append(
                            "SUM(CASE WHEN LOWER(IFNULL(`status`,'')) IN ('failed','reject','rejected','invalid') "
                            "OR LOWER(IFNULL(`status`,'')) LIKE '%fail%' THEN 1 ELSE 0 END) AS failed"
                        )
                        parts.append(
                            "SUM(CASE WHEN LOWER(IFNULL(`status`,'')) LIKE '%block%' "
                            "OR LOWER(IFNULL(`status`,'')) IN ('rejected','reject') THEN 1 ELSE 0 END) AS blocked"
                        )
                    spam_bits = []
                    if "classification" in present:
                        spam_bits.append("LOWER(IFNULL(`classification`,'')) LIKE '%spam%'")
                    if "spam_score" in present:
                        spam_bits.append("`spam_score` >= 5")
                    if spam_bits:
                        parts.append(f"SUM(CASE WHEN {' OR '.join(spam_bits)} THEN 1 ELSE 0 END) AS spam")
                    agg = (
                        conn.execute(
                            text(
                                f"SELECT {', '.join(parts)} FROM `{LOG_TABLE}` "
                                "WHERE `log_datetime` >= :since"
                            ),
                            {"since": since},
                        )
                        .mappings()
                        .first()
                    )
                    if agg:
                        totals["log_total"] = _int(agg.get("log_total")) or 0
                        totals["inbound"] = _int(agg.get("inbound")) or 0
                        totals["outbound"] = _int(agg.get("outbound")) or 0
                        totals["delivered"] = _int(agg.get("delivered")) or 0
                        totals["failed"] = _int(agg.get("failed")) or 0
                        totals["blocked"] = _int(agg.get("blocked")) or 0
                        totals["spam"] = _int(agg.get("spam")) or 0
                        if not totals["sent"]:
                            totals["sent"] = totals["delivered"]
                        if not totals["bounce"]:
                            totals["bounce"] = _int(agg.get("bounced")) or 0
                        if not totals["deferred"]:
                            totals["deferred"] = _int(agg.get("deferred")) or 0

                    event_cols = [c for c in LOG_COLS if c in present]
                    if event_cols:
                        quoted = ", ".join(f"`{c}`" for c in event_cols)
                        log_rows = (
                            conn.execute(
                                text(
                                    f"SELECT {quoted} FROM `{LOG_TABLE}` "
                                    "WHERE `log_datetime` >= :since "
                                    "ORDER BY `log_datetime` DESC LIMIT 80"
                                ),
                                {"since": since},
                            )
                            .mappings()
                            .all()
                        )
                        events = [map_event(dict(row)) for row in log_rows]

            if _table_exists(conn, QUARANTINE_TABLE):
                found = True
                totals["quarantine"] = _int(conn.execute(text(f"SELECT COUNT(*) FROM `{QUARANTINE_TABLE}`")).scalar()) or 0
            if _table_exists(conn, CAMPAIGN_QUEUE_TABLE):
                found = True
                totals["campaign_queued"] = (
                    _int(conn.execute(text(f"SELECT COUNT(*) FROM `{CAMPAIGN_QUEUE_TABLE}`")).scalar()) or 0
                )
    except Exception as exc:
        return _empty(str(exc)[:240], hours=hours, database=database)

    if not found:
        return _empty("expected campaign tables not found", hours=hours, database=database)

    return {
        "ok": True,
        "reason": None,
        "database": database,
        "period_hours": hours,
        "totals": totals,
        "queue": sum_queue(servers),
        "servers": servers,
        "events": events,
    }
