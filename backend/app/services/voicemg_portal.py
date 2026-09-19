"""Read-only extra metrics from MariaDB `voicemg`.

Used to enrich the existing VoiceMG SSH table and Server cards — no new portal tabs.
Never selects password / secret / token columns.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.db.legacy_metrics_session import get_legacy_metrics_engine

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


def _engine():
    if not settings.legacy_metrics_database_url:
        return None, "LEGACY_METRICS_DATABASE_URL not set"
    database = settings.legacy_voicemg_database or "voicemg"
    engine = get_legacy_metrics_engine(database)
    if engine is None:
        return None, "engine unavailable"
    return engine, database


def _empty(reason: str, database: str | None = None) -> dict:
    return {"ok": False, "reason": reason, "database": database, "servers": []}


def _safe_columns(conn, table: str) -> list[str]:
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


def _select(alias: str, cols: list[str], prefix: str = "") -> str:
    parts = []
    for col in cols:
        as_name = f"{prefix}{col}" if prefix else col
        parts.append(f"{alias}.`{col}` AS `{as_name}`")
    return ", ".join(parts)


def _latest_join(alias: str, table: str, cols: list[str], prefix: str) -> tuple[str, str]:
    if (
        not cols
        or "id" not in cols
        or "server_id" not in cols
        or not _IDENT.match(table)
        or not _IDENT.match(alias)
    ):
        return "", ""
    select_cols = [c for c in cols if c != "id"]
    select = ", " + _select(alias, select_cols, prefix) if select_cols else ""
    latest = f"{alias}_latest"
    join = f"""
                LEFT JOIN (
                  SELECT t.*
                  FROM `{table}` t
                  INNER JOIN (
                    SELECT server_id, MAX(id) AS max_id
                    FROM `{table}`
                    GROUP BY server_id
                  ) {latest} ON {latest}.max_id = t.id
                ) {alias} ON {alias}.server_id = s.id
    """
    return select, join


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(number)


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text_val = str(value).strip()
    return text_val or None


def _first(row, *names: str):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def _table_exists(conn, name: str) -> bool:
    count = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl"
        ),
        {"tbl": name},
    ).scalar()
    return bool(count)


def _fmt_mb(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"


def mem_label(used: float | None, total: float | None) -> str | None:
    if used is None and total is None:
        return None
    if used is not None and total is not None:
        return f"{_fmt_mb(used)}/{_fmt_mb(total)} MB"
    if used is not None:
        return f"{_fmt_mb(used)} MB used"
    return f"{_fmt_mb(total)} MB total"  # type: ignore[arg-type]


def fetch_voicemg_extras() -> dict:
    engine, extra = _engine()
    if engine is None:
        return _empty(extra)
    database = extra
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("SET SESSION max_execution_time = 10000"))
            except Exception:
                pass
            if not _table_exists(conn, "servers"):
                return _empty("servers table not found", database)

            server_cols = _safe_columns(conn, "servers")
            if "id" not in server_cols:
                return _empty("servers.id missing", database)

            system_cols = _safe_columns(conn, "metrics_system") if _table_exists(conn, "metrics_system") else []
            calls_cols = _safe_columns(conn, "metrics_calls") if _table_exists(conn, "metrics_calls") else []
            disk_cols = _safe_columns(conn, "metrics_disk") if _table_exists(conn, "metrics_disk") else []

            system_select, system_join = _latest_join("sys", "metrics_system", system_cols, "sys_")
            calls_select, calls_join = _latest_join("c", "metrics_calls", calls_cols, "c_")
            disk_select, disk_join = _latest_join("d", "metrics_disk", disk_cols, "d_")

            order_col = "hostname" if "hostname" in server_cols else "id"
            sql = text(
                f"SELECT {_select('s', server_cols)}"
                + system_select
                + calls_select
                + disk_select
                + """
                FROM servers s
                """
                + system_join
                + calls_join
                + disk_join
                + f" ORDER BY s.`{order_col}`"
            )
            rows = conn.execute(sql).mappings().all()

        servers = [_map_server(row) for row in rows]
        return {"ok": True, "database": database, "reason": None, "servers": servers}
    except Exception as exc:
        return _empty(str(exc), database)


def _map_server(row) -> dict:
    server_id = int(row["id"])
    hostname = _str(_first(row, "hostname", "server_name", "name")) or f"voicemg-{server_id}"
    ip = _str(_first(row, "ip_address", "ip", "host")) or ""
    used = _num(_first(row, "sys_mem_used_mb", "mem_used_mb"))
    total = _num(_first(row, "sys_mem_total_mb", "mem_total_mb"))
    return {
        "id": server_id,
        "hostname": hostname,
        "ip": ip,
        "ip_address": ip,
        "product": _str(_first(row, "product")),
        "role": _str(_first(row, "role")),
        "cpu_pct": _num(_first(row, "sys_cpu_pct", "cpu_pct")),
        "load1": _num(_first(row, "sys_load1", "load1")),
        "mem_used_mb": used,
        "mem_total_mb": total,
        "mem": mem_label(used, total),
        "active_calls": _int(_first(row, "c_active_calls", "active_calls")),
        "rtp_sessions": _int(_first(row, "c_rtp_sessions", "rtp_sessions")),
        "rtp_mbps_out": _num(_first(row, "c_rtp_mbps_out", "rtp_mbps_out")),
        "rtp_mbps_in": _num(_first(row, "c_rtp_mbps_in", "rtp_mbps_in")),
        "jitter_ms": _num(_first(row, "c_jitter_ms", "jitter_ms")),
        "pkts_lost_delta": _num(_first(row, "c_pkts_lost_delta", "pkts_lost_delta")),
        "disk_used_pct": _num(_first(row, "d_used_pct", "d_disk_used_pct", "used_pct")),
        "disk_mount": _str(_first(row, "d_mount", "d_mountpoint", "mount")),
        "recorded_at": _first(row, "c_ts", "sys_ts", "d_ts", "ts"),
    }
