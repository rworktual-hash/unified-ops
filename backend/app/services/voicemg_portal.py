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


def _latest_row(conn, table: str, cols: list[str], server_id: int) -> dict:
    if not cols or "id" not in cols or not _IDENT.match(table):
        return {}
    select_cols = [c for c in cols if _IDENT.match(c)]
    if not select_cols:
        return {}
    quoted = ", ".join(f"`{c}`" for c in select_cols)
    row = conn.execute(
        text(
            f"SELECT {quoted} FROM `{table}` "
            "WHERE server_id = :sid ORDER BY id DESC LIMIT 1"
        ),
        {"sid": server_id},
    ).mappings().first()
    return dict(row) if row else {}


def _prefixed(row: dict, prefix: str) -> dict:
    return {f"{prefix}{key}": value for key, value in row.items() if key != "id"}


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


def product_group(hostname: str, product: str | None) -> str:
    name = hostname.lower().replace("_", "-")
    prod = (product or "").lower()
    if "ai" in prod or name.startswith("ai-") or "aivmg" in name.replace("-", ""):
        return "ai_ccaas"
    return "ccaas"


def _find_num(row, *needles: str, exclude: tuple[str, ...] = ()) -> float | None:
    for key, val in row.items():
        lowered = str(key).lower()
        if any(part in lowered for part in exclude):
            continue
        if any(needle in lowered for needle in needles):
            number = _num(val)
            if number is not None:
                return number
    return None


def _latest_process_udp(conn, cols: list[str], server_id: int) -> dict:
    if "ts" not in cols or not _IDENT.match("metrics_process"):
        return {}
    latest = conn.execute(
        text("SELECT ts FROM metrics_process WHERE server_id = :sid ORDER BY id DESC LIMIT 1"),
        {"sid": server_id},
    ).first()
    if not latest:
        return {}
    parts: list[str] = []
    if "udp_active" in cols:
        parts.append("SUM(udp_active) AS udp_active")
    if "udp_inactive" in cols:
        parts.append("SUM(udp_inactive) AS udp_inactive")
    if not parts:
        return {}
    row = conn.execute(
        text(
            f"SELECT {', '.join(parts)} FROM metrics_process "
            "WHERE server_id = :sid AND ts = :ts"
        ),
        {"sid": server_id, "ts": latest[0]},
    ).mappings().first()
    return _prefixed(dict(row), "p_") if row else {}


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
            process_cols = (
                _safe_columns(conn, "metrics_process") if _table_exists(conn, "metrics_process") else []
            )

            order_col = "hostname" if "hostname" in server_cols else "id"
            host_rows = conn.execute(
                text(f"SELECT {_select('s', server_cols)} FROM servers s ORDER BY s.`{order_col}` LIMIT 40")
            ).mappings().all()

            rows = []
            for host in host_rows:
                server_id = _int(host.get("id"))
                if server_id is None:
                    continue
                merged = dict(host)
                if system_cols:
                    merged.update(_prefixed(_latest_row(conn, "metrics_system", system_cols, server_id), "sys_"))
                if calls_cols:
                    merged.update(_prefixed(_latest_row(conn, "metrics_calls", calls_cols, server_id), "c_"))
                if process_cols:
                    merged.update(_latest_process_udp(conn, process_cols, server_id))
                rows.append(merged)

        servers = [_map_server(row) for row in rows]
        return {"ok": True, "database": database, "reason": None, "servers": servers}
    except Exception as exc:
        return _empty(str(exc), database)


def _map_server(row) -> dict:
    server_id = int(row["id"])
    hostname = _str(_first(row, "hostname", "server_name", "name")) or f"voicemg-{server_id}"
    ip = _str(_first(row, "ip_address", "ip", "host")) or ""
    product = _str(_first(row, "product"))
    used = _num(_first(row, "sys_mem_used_mb", "mem_used_mb"))
    total = _num(_first(row, "sys_mem_total_mb", "mem_total_mb"))
    sent = _num(_first(row, "c_pkts_sent_ps", "pkts_sent_ps"))
    recv = _num(_first(row, "c_pkts_recv_ps", "pkts_recv_ps"))
    lost = _num(_first(row, "c_pkts_lost_delta", "pkts_lost_delta"))
    loss = _num(_first(row, "c_pkt_loss_pct", "pkt_loss_pct")) or _find_num(
        row, "loss_pct", "packet_loss", "loss_percent"
    )
    if loss is None and lost is not None:
        denom = (sent or 0) + (recv or 0)
        if denom > 0:
            loss = 100.0 * lost / denom
    stall = _int(
        _find_num(row, "stall")
        if _find_num(row, "stall") is not None
        else _first(row, "p_udp_inactive", "udp_inactive")
    )
    mos = _num(_first(row, "c_mos", "mos")) or _find_num(row, "mos")
    quality_source = _str(_first(row, "c_quality_source", "quality_source"))
    rtcp = quality_source or _str(_first(row, "c_rtcp", "rtcp"))
    if not rtcp and (_find_num(row, "rtcp") or 0) > 0:
        rtcp = "rtcp"
    return {
        "id": server_id,
        "hostname": hostname,
        "ip": ip,
        "ip_address": ip,
        "product": product,
        "role": _str(_first(row, "role")),
        "group": product_group(hostname, product),
        "cpu_pct": _num(_first(row, "sys_cpu_pct", "cpu_pct")),
        "load1": _num(_first(row, "sys_load1", "load1")),
        "mem_used_mb": used,
        "mem_total_mb": total,
        "mem": mem_label(used, total),
        "mem_pct": (100.0 * used / total) if used is not None and total else None,
        "active_calls": _int(_first(row, "c_active_calls", "active_calls")),
        "rtp_sessions": _int(_first(row, "c_rtp_sessions", "rtp_sessions")),
        "rtp_mbps_out": _num(_first(row, "c_rtp_mbps_out", "rtp_mbps_out")),
        "rtp_mbps_in": _num(_first(row, "c_rtp_mbps_in", "rtp_mbps_in")),
        "rtp_mbps_exp": _find_num(row, "rtp_mbps_exp", "expected_rtp", "rtp_exp"),
        "jitter_ms": _num(_first(row, "c_jitter_ms", "jitter_ms")),
        "pkts_lost_delta": lost,
        "pkts_sent_ps": sent,
        "pkts_recv_ps": recv,
        "packet_loss_pct": loss,
        "mos": mos,
        "stall": stall,
        "udp_active": _int(_first(row, "p_udp_active", "udp_active")),
        "udp_inactive": _int(_first(row, "p_udp_inactive", "udp_inactive")),
        "quality_source": quality_source,
        "rtcp": rtcp,
        "disk_used_pct": _num(_first(row, "d_used_pct", "d_disk_used_pct", "used_pct")),
        "disk_mount": _str(_first(row, "d_mount", "d_mountpoint", "mount")),
        "recorded_at": _first(row, "c_ts", "sys_ts", "p_ts", "d_ts", "ts"),
    }
