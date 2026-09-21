"""Read-only extra metrics from MariaDB `voicemg`.

Used to enrich the existing VoiceMG SSH table and Server cards — no new portal tabs.
Never selects password / secret / token columns.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.db.legacy_metrics_session import get_legacy_metrics_engine
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
    if not cols or not _IDENT.match(table):
        return {}
    order = "id" if "id" in cols else "ts" if "ts" in cols else None
    if not order:
        return {}
    select_cols = [c for c in cols if _IDENT.match(c)]
    if not select_cols:
        return {}
    quoted = ", ".join(f"`{c}`" for c in select_cols)
    row = conn.execute(
        text(
            f"SELECT {quoted} FROM `{table}` "
            f"WHERE server_id = :sid ORDER BY `{order}` DESC LIMIT 1"
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


_PROCESS_SUM = ("udp_active", "udp_inactive", "udp_sockets", "open_fds", "threads")
_PROCESS_AVG = ("cpu_pct", "mem_pct", "proc_cpu_pct", "proc_mem_pct")
_EXTRA_TABLES = (
    ("metrics_disk", "d_"),
    ("metrics_net", "n_"),
    ("metrics_kernel", "k_"),
    ("metrics_ipc", "i_"),
    ("metrics_gateway", "gw_"),
)


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
    for name in _PROCESS_SUM:
        if name in cols:
            parts.append(f"SUM(`{name}`) AS `{name}`")
    for name in _PROCESS_AVG:
        if name in cols:
            parts.append(f"AVG(`{name}`) AS `{name}`")
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
    cached = get_cached("voicemg_extras")
    if cached is not None:
        return cached
    out = _fetch_voicemg_extras()
    set_cached("voicemg_extras", out)
    return out


def _fetch_voicemg_extras() -> dict:
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
            extra_cols = {
                table: _safe_columns(conn, table) if _table_exists(conn, table) else []
                for table, _prefix in _EXTRA_TABLES
            }

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
                for table, prefix in _EXTRA_TABLES:
                    cols = extra_cols.get(table) or []
                    if cols:
                        merged.update(_prefixed(_latest_row(conn, table, cols, server_id), prefix))
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
        "disk_used_pct": _disk_used_pct(row),
        "disk_mount": _str(_first(row, "d_mount", "d_mountpoint", "mount")),
        "rx_errors": _find_num(row, "rx_err", exclude=("tx",)),
        "rx_drops": _find_num(row, "rx_drop", exclude=("tx",)),
        "open_fds": _int(_first(row, "p_open_fds", "open_fds"))
        or _int(_find_num(row, "open_fd", "fd_count")),
        "threads": _int(_first(row, "p_threads", "threads"))
        or _int(_find_num(row, "thread", exclude=("_id",))),
        "ipc_sent_ps": _find_num(row, "sent_ps", "ipc_sent", "msg_sent"),
        "ipc_recv_ps": _find_num(row, "recv_ps", "ipc_recv", "msg_recv"),
        "ipc_latency_ms": _find_num(row, "latency_ms", "ipc_latency"),
        "runqueue": _find_num(row, "runqueue", "nr_running"),
        "buffers_mb": _find_num(row, "buffers"),
        "cached_mb": _find_num(row, "cached", exclude=("cache_hit",)),
        "udp_pps_in": _find_num(row, "udp_pps_in", "udp_in_pps"),
        "udp_pps_out": _find_num(row, "udp_pps_out", "udp_out_pps"),
        "nic_rx_mbps": _find_num(row, "nic_rx", exclude=("rtp",))
        or _find_num(row, "n_rx_mbps", "n_rx_bps"),
        "nic_tx_mbps": _find_num(row, "nic_tx", exclude=("rtp",))
        or _find_num(row, "n_tx_mbps", "n_tx_bps"),
        "proc_cpu_pct": _num(_first(row, "p_cpu_pct", "p_proc_cpu_pct", "gw_cpu_pct"))
        or _find_num(row, "proc_cpu", "gw_cpu"),
        "proc_mem_pct": _num(_first(row, "p_mem_pct", "p_proc_mem_pct", "gw_mem_pct"))
        or _find_num(row, "proc_mem", "gw_mem"),
        "udp_sockets": _int(_first(row, "p_udp_sockets", "udp_sockets"))
        or _int(_first(row, "p_udp_active", "udp_active")),
        "rtp_gb": _rtp_gb(row),
        "recorded_at": _first(row, "c_ts", "sys_ts", "p_ts", "d_ts", "n_ts", "k_ts", "i_ts", "ts"),
    }


def _disk_used_pct(row) -> float | None:
    disk = _num(_first(row, "d_used_pct", "d_disk_used_pct", "sys_disk_used_pct", "used_pct"))
    if disk is not None:
        return disk
    return _find_num(row, "disk_used", "disk_pct")


def _rtp_gb(row) -> float | None:
    gb = _find_num(row, "rtp_gb")
    if gb is not None:
        return gb
    raw = _find_num(row, "rtp_bytes")
    if raw is None:
        return None
    return raw / 1_000_000_000 if raw > 10_000 else raw


HISTORY_RANGES = {
    "5m",
    "30m",
    "1h",
    "2h",
    "6h",
    "12h",
    "today",
    "yesterday",
    "2d",
    "week",
    "custom",
}
HISTORY_GROUPS = {"all", "ai_ccaas", "ccaas"}
_CALL_METRICS = (
    "active_calls",
    "rtp_sessions",
    "rtp_mbps_out",
    "rtp_mbps_in",
    "rtp_mbps_exp",
    "jitter_ms",
    "pkt_loss_pct",
    "mos",
    "pkts_lost_delta",
    "pkts_sent_ps",
    "pkts_recv_ps",
    "stalled_udp",
    "rtp_gb",
    "udp_pps_in",
    "udp_pps_out",
)
_SYS_METRICS = (
    "cpu_pct",
    "load1",
    "mem_used_mb",
    "mem_total_mb",
    "mem_pct",
    "disk_used_pct",
    "rx_errors",
    "rx_drops",
    "tx_errors",
    "open_fds",
    "threads",
    "nic_rx_mbps",
    "nic_tx_mbps",
    "rx_mbps",
    "tx_mbps",
    "sent_ps",
    "recv_ps",
    "latency_ms",
    "runqueue",
    "buffers_mb",
    "cached_mb",
    "proc_cpu_pct",
    "proc_mem_pct",
)
_HISTORY_FIELDS = (
    "active_calls",
    "mos",
    "jitter_ms",
    "packet_loss_pct",
    "rtp_mbps",
    "rtp_mbps_in",
    "rtp_mbps_out",
    "rtp_mbps_exp",
    "cpu_pct",
    "mem_pct",
    "rx_errors",
    "rx_drops",
    "open_fds",
    "threads",
    "ipc_sent_ps",
    "ipc_recv_ps",
    "ipc_latency_ms",
    "runqueue",
    "buffers_mb",
    "cached_mb",
    "udp_pps_in",
    "udp_pps_out",
    "nic_rx_mbps",
    "nic_tx_mbps",
    "proc_cpu_pct",
    "proc_mem_pct",
    "udp_sockets",
    "rtp_gb",
    "disk_used_pct",
)
_FLEET_SUM = {
    "active_calls",
    "rtp_mbps",
    "rtp_mbps_in",
    "rtp_mbps_out",
    "rtp_mbps_exp",
    "udp_pps_in",
    "udp_pps_out",
    "rx_errors",
    "rx_drops",
    "ipc_sent_ps",
    "ipc_recv_ps",
    "rtp_gb",
    "udp_sockets",
    "open_fds",
    "threads",
}
_NUMERIC_HINTS = (
    "pct",
    "mb",
    "ms",
    "cpu",
    "mem",
    "rx",
    "tx",
    "udp",
    "rtp",
    "jitter",
    "mos",
    "load",
    "fd",
    "thread",
    "latenc",
    "sent",
    "recv",
    "drop",
    "err",
    "pps",
    "queue",
    "buffer",
    "cache",
    "socket",
    "stall",
    "call",
    "session",
    "pkt",
    "nic",
    "ctx",
    "run",
    "used",
    "active",
    "inact",
    "gb",
    "byte",
    "loss",
    "count",
)
_WINDOW_SKIP = {
    "id",
    "server_id",
    "ts",
    "hostname",
    "name",
    "product",
    "role",
    "ip",
    "ip_address",
    "mount",
    "mountpoint",
}


def _empty_history(
    reason: str,
    range_id: str = "5m",
    group: str = "all",
    database: str | None = None,
) -> dict:
    return {
        "ok": False,
        "reason": reason,
        "database": database,
        "range": range_id,
        "group": group,
        "since": None,
        "until": None,
        "bucket_seconds": 60,
        "host_count": 0,
        "point_count": 0,
        "points": [],
        "server_id": None,
        "host_name": None,
    }


def history_window(
    range_id: str,
    now: datetime,
    today,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[datetime, datetime, int]:
    """Return (since, until, bucket_seconds) using MariaDB clock values."""
    start_of_today = datetime.combine(today, datetime.min.time())
    if range_id == "5m":
        return now - timedelta(minutes=5), now, 10
    if range_id == "30m":
        return now - timedelta(minutes=30), now, 30
    if range_id == "1h":
        return now - timedelta(hours=1), now, 60
    if range_id == "2h":
        return now - timedelta(hours=2), now, 60
    if range_id == "6h":
        return now - timedelta(hours=6), now, 120
    if range_id == "12h":
        return now - timedelta(hours=12), now, 300
    if range_id == "today":
        return start_of_today, now, 300
    if range_id == "yesterday":
        return start_of_today - timedelta(days=1), start_of_today - timedelta(seconds=1), 300
    if range_id == "2d":
        return now - timedelta(days=2), now, 600
    if range_id == "week":
        return now - timedelta(days=7), now, 1800
    if range_id == "custom" and start:
        until = end or now
        if until <= start:
            until = start + timedelta(minutes=5)
        span = max((until - start).total_seconds(), 300)
        bucket = 10 if span <= 900 else 60 if span <= 7200 else 300 if span <= 86400 else 1800
        return start, until, bucket
    return now - timedelta(minutes=5), now, 10


def parse_history_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def _as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return None


def downsample_rows(rows: list[dict], max_points: int) -> list[dict]:
    if max_points <= 0 or len(rows) <= max_points:
        return rows
    if max_points == 1:
        return [rows[-1]]
    last_idx = len(rows) - 1
    out: list[dict] = []
    seen: set[int] = set()
    for i in range(max_points):
        idx = round(i * last_idx / (max_points - 1))
        if idx in seen:
            continue
        seen.add(idx)
        out.append(rows[idx])
    return out


def _bucket_key(ts: Any, seconds: int) -> datetime | None:
    dt = _as_dt(ts)
    if dt is None or seconds <= 0:
        return None
    epoch = int(dt.replace(tzinfo=None).timestamp())
    snapped = epoch - (epoch % seconds)
    return datetime.fromtimestamp(snapped)


def map_history_sample(row: dict) -> dict:
    sent = _num(_first(row, "pkts_sent_ps"))
    recv = _num(_first(row, "pkts_recv_ps"))
    lost = _num(_first(row, "pkts_lost_delta"))
    loss = _num(_first(row, "pkt_loss_pct", "packet_loss_pct"))
    if loss is None and lost is not None:
        denom = (sent or 0) + (recv or 0)
        if denom > 0:
            loss = 100.0 * lost / denom
    rtp_out = _num(_first(row, "rtp_mbps_out"))
    rtp_in = _num(_first(row, "rtp_mbps_in"))
    rtp = _num(_first(row, "rtp_mbps"))
    if rtp is None and (rtp_out is not None or rtp_in is not None):
        rtp = (rtp_out or 0) + (rtp_in or 0)
    used = _num(_first(row, "mem_used_mb"))
    total = _num(_first(row, "mem_total_mb"))
    mem_pct = _num(_first(row, "mem_pct"))
    if mem_pct is None and used is not None and total:
        mem_pct = 100.0 * used / total
    return {
        "ts": _as_dt(_first(row, "ts")),
        "active_calls": _num(_first(row, "active_calls")),
        "mos": _num(_first(row, "mos")),
        "jitter_ms": _num(_first(row, "jitter_ms")),
        "packet_loss_pct": loss,
        "rtp_mbps": rtp,
        "rtp_mbps_in": rtp_in,
        "rtp_mbps_out": rtp_out,
        "rtp_mbps_exp": _num(_first(row, "rtp_mbps_exp"))
        or _find_num(row, "expected_rtp", "rtp_exp"),
        "cpu_pct": _num(_first(row, "cpu_pct")),
        "mem_pct": mem_pct,
        "rx_errors": _find_num(row, "rx_err", exclude=("tx",)),
        "rx_drops": _find_num(row, "rx_drop", exclude=("tx",)),
        "open_fds": _num(_first(row, "open_fds")) or _find_num(row, "open_fd", "fd_count"),
        "threads": _num(_first(row, "threads")) or _find_num(row, "thread", exclude=("_id",)),
        "ipc_sent_ps": _find_num(row, "sent_ps", "ipc_sent", "msg_sent"),
        "ipc_recv_ps": _find_num(row, "recv_ps", "ipc_recv", "msg_recv"),
        "ipc_latency_ms": _find_num(row, "latency_ms", "ipc_latency"),
        "runqueue": _find_num(row, "runqueue", "nr_running"),
        "buffers_mb": _find_num(row, "buffers"),
        "cached_mb": _find_num(row, "cached", exclude=("cache_hit",)),
        "udp_pps_in": _find_num(row, "udp_pps_in", "udp_in_pps"),
        "udp_pps_out": _find_num(row, "udp_pps_out", "udp_out_pps"),
        "nic_rx_mbps": _find_num(row, "nic_rx", exclude=("rtp",))
        or _num(_first(row, "rx_mbps", "n_rx_mbps")),
        "nic_tx_mbps": _find_num(row, "nic_tx", exclude=("rtp",))
        or _num(_first(row, "tx_mbps", "n_tx_mbps")),
        "proc_cpu_pct": _num(_first(row, "proc_cpu_pct"))
        or _find_num(row, "proc_cpu", "gw_cpu"),
        "proc_mem_pct": _num(_first(row, "proc_mem_pct")) or _find_num(row, "proc_mem", "gw_mem"),
        "udp_sockets": _num(_first(row, "udp_sockets", "udp_active")),
        "rtp_gb": _rtp_gb(row),
        "disk_used_pct": _num(_first(row, "disk_used_pct", "used_pct"))
        or _find_num(row, "disk_used", "disk_pct"),
    }


def merge_host_series(
    call_rows: list[dict],
    sys_rows: list[dict],
    bucket_seconds: int,
    max_points: int = 120,
    extra_rows: list[dict] | None = None,
) -> list[dict]:
    by_ts: dict[datetime, dict] = {}
    for raw in call_rows + sys_rows + (extra_rows or []):
        sample = map_history_sample(raw)
        key = _bucket_key(sample["ts"], bucket_seconds)
        if key is None:
            continue
        prev = by_ts.get(key, {"ts": key})
        for field in _HISTORY_FIELDS:
            if sample.get(field) is not None:
                prev[field] = sample[field]
        by_ts[key] = prev
    ordered = [by_ts[key] for key in sorted(by_ts)]
    return downsample_rows(ordered, max_points)


def _avg_num(values) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 3)


def _sum_num(values) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums), 3)


def fleet_points(host_series: list[list[dict]]) -> list[dict]:
    buckets: dict[datetime, list[dict]] = defaultdict(list)
    for series in host_series:
        for point in series:
            ts = point.get("ts")
            if isinstance(ts, datetime):
                buckets[ts].append(point)
    out = []
    for ts in sorted(buckets):
        samples = buckets[ts]
        point = {"ts": ts}
        for field in _HISTORY_FIELDS:
            values = (s.get(field) for s in samples)
            point[field] = _sum_num(values) if field in _FLEET_SUM else _avg_num(values)
        out.append(point)
    return out


def fetch_voicemg_history(
    range_id: str = "5m",
    group: str = "all",
    start: str | None = None,
    end: str | None = None,
    server_id: int | None = None,
) -> dict:
    range_id = range_id if range_id in HISTORY_RANGES else "5m"
    group = group if group in HISTORY_GROUPS else "all"
    cache_key = f"voicemg_history:{range_id}:{group}:{start or ''}:{end or ''}:{server_id or 'all'}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    out = _fetch_voicemg_history(
        range_id, group, parse_history_dt(start), parse_history_dt(end), server_id
    )
    set_cached(cache_key, out)
    return out


def _fetch_voicemg_history(
    range_id: str,
    group: str,
    start: datetime | None = None,
    end: datetime | None = None,
    server_id: int | None = None,
) -> dict:
    engine, extra = _engine()
    if engine is None:
        return _empty_history(extra, range_id, group)
    database = extra
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("SET SESSION max_execution_time = 15000"))
            except Exception:
                pass
            clock = conn.execute(text("SELECT NOW() AS now, CURDATE() AS today")).mappings().first()
            now = clock["now"] if clock else datetime.now()
            today = clock["today"] if clock else now.date()
            since, until, bucket_seconds = history_window(range_id, now, today, start, end)
            if not _table_exists(conn, "servers"):
                return _empty_history("servers table not found", range_id, group, database)
            server_cols = _safe_columns(conn, "servers")
            if "id" not in server_cols:
                return _empty_history("servers.id missing", range_id, group, database)
            system_cols = (
                _safe_columns(conn, "metrics_system") if _table_exists(conn, "metrics_system") else []
            )
            calls_cols = (
                _safe_columns(conn, "metrics_calls") if _table_exists(conn, "metrics_calls") else []
            )
            order_col = "hostname" if "hostname" in server_cols else "id"
            host_rows = (
                conn.execute(
                    text(
                        f"SELECT {_select('s', server_cols)} FROM servers s "
                        f"ORDER BY s.`{order_col}` LIMIT 40"
                    )
                )
                .mappings()
                .all()
            )
            extra_tables = [("metrics_process",)] + [(name,) for name, _prefix in _EXTRA_TABLES]
            extra_cols: dict[str, list[str]] = {}
            for (table,) in extra_tables:
                extra_cols[table] = _safe_columns(conn, table) if _table_exists(conn, table) else []
            series: list[list[dict]] = []
            host_count = 0
            matched_name: str | None = None
            for host in host_rows:
                hid = _int(host.get("id"))
                if hid is None:
                    continue
                if server_id is not None and hid != server_id:
                    continue
                hostname = _str(_first(host, "hostname", "server_name", "name")) or ""
                if group != "all" and product_group(hostname, _str(host.get("product"))) != group:
                    continue
                host_count += 1
                matched_name = hostname
                call_rows = _window_rows(
                    conn, "metrics_calls", calls_cols, hid, since, until, bucket_seconds
                )
                sys_rows = _window_rows(
                    conn, "metrics_system", system_cols, hid, since, until, bucket_seconds
                )
                extra_rows: list[dict] = []
                for table, cols in extra_cols.items():
                    extra_rows.extend(
                        _window_rows(conn, table, cols, hid, since, until, bucket_seconds)
                    )
                series.append(
                    merge_host_series(call_rows, sys_rows, bucket_seconds, extra_rows=extra_rows)
                )
        points = series[0] if server_id is not None and len(series) == 1 else fleet_points(series)
        return {
            "ok": True,
            "reason": None,
            "database": database,
            "range": range_id,
            "group": group,
            "since": since,
            "until": until,
            "bucket_seconds": bucket_seconds,
            "host_count": host_count,
            "point_count": len(points),
            "points": points,
            "server_id": server_id,
            "host_name": matched_name if server_id is not None else None,
        }
    except Exception as exc:
        return _empty_history(str(exc), range_id, group, database)


def _window_metric_names(cols: list[str]) -> list[str]:
    named = [name for name in _CALL_METRICS + _SYS_METRICS if name in cols]
    extra = [
        name
        for name in cols
        if name not in named
        and name not in _WINDOW_SKIP
        and any(hint in name.lower() for hint in _NUMERIC_HINTS)
    ]
    return named + extra


def _window_rows(
    conn,
    table: str,
    cols: list[str],
    server_id: int,
    since: datetime,
    until: datetime,
    bucket_seconds: int,
) -> list[dict]:
    if not cols or "ts" not in cols or "server_id" not in cols:
        return []
    if not _IDENT.match(table) or bucket_seconds <= 0:
        return []
    avgs = [
        f"AVG(`{name}`) AS `{name}`"
        for name in _window_metric_names(cols)
        if _IDENT.match(name)
    ]
    if not avgs:
        return []
    rows = (
        conn.execute(
            text(
                f"SELECT FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(ts) / :b) * :b) AS ts, "
                f"{', '.join(avgs)} FROM `{table}` "
                "WHERE server_id = :sid AND ts >= :since AND ts <= :until "
                "GROUP BY 1 ORDER BY 1 LIMIT 400"
            ),
            {"sid": server_id, "since": since, "until": until, "b": bucket_seconds},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
