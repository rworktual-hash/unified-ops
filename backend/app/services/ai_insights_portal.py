"""Read-only extra metrics from MariaDB `ai_insights_platform`.

Used to enrich existing Server cards and SSH tables — no new portal tabs.
Never selects password / secret / token columns.
"""

from __future__ import annotations

import json
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
_PRIORITY_KEYS = (
    "qps",
    "queries_per_sec",
    "threads",
    "threads_connected",
    "slow_queries",
    "buffer_hit",
    "buffer_hit_pct",
    "buffer_pool_hit",
    "sip_udp_5060_listen",
    "sip_udp_listen",
    "sip_udp_flows",
    "sip_accept_pps",
    "sip_accept_packets",
    "sip_firewall_drop",
    "sip_firewall_drop_pps",
    "sip_drop_packets",
    "sip_drop_pps",
    "ippbx_procs",
    "ippbx_processes",
    "app_listen_port",
    "app_clients",
    "app_processes",
    "listen_sockets",
    "listen_port",
    "tcp_established",
    "tcp_clients",
    "mysql_conns",
    "mysql_connections",
    "connections",
    "workers",
    "worker_processes",
    "gpu_utilization",
    "gpu_temperature",
    "gpu_util",
    "gpu_temp",
    "load_average",
    "cpu_utilization",
    "memory_utilization",
)


def _engine():
    if not settings.legacy_metrics_database_url:
        return None, "LEGACY_METRICS_DATABASE_URL not set"
    database = settings.legacy_ai_insights_database or "ai_insights_platform"
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


def _label(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").strip()


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def flatten_service_payload(raw: Any, limit: int = 10) -> list[dict]:
    """Turn latest ai_service_metrics.payload JSON into short display tiles."""
    data = raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        text_val = raw.strip()
        if not text_val:
            return []
        try:
            data = json.loads(text_val)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, dict):
        return []

    flat: dict[str, Any] = {}

    def take(key: str, value: Any) -> None:
        if not key or _is_secret_key(key) or key in flat:
            return
        if isinstance(value, bool):
            flat[key] = "yes" if value else "no"
            return
        if isinstance(value, (int, float)):
            flat[key] = value
            return
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed and len(trimmed) <= 80:
                flat[key] = trimmed

    for key, value in data.items():
        if isinstance(value, dict):
            for inner_key, inner_val in value.items():
                take(f"{key}_{inner_key}" if inner_key else str(key), inner_val)
        else:
            take(str(key), value)

    ordered: list[dict] = []
    seen: set[str] = set()
    for key in _PRIORITY_KEYS:
        if key in flat and key not in seen:
            ordered.append({"key": key, "label": _label(key), "value": str(flat[key])})
            seen.add(key)
    for key, value in flat.items():
        if key in seen:
            continue
        ordered.append({"key": key, "label": _label(key), "value": str(value)})
        seen.add(key)
        if len(ordered) >= limit:
            break
    return ordered[:limit]


def fetch_ai_insights_extras() -> dict:
    engine, extra = _engine()
    if engine is None:
        return _empty(extra)
    database = extra
    try:
        with engine.connect() as conn:
            if not _table_exists(conn, "ai_servers"):
                return _empty("ai_servers table not found", database)

            server_cols = _safe_columns(conn, "ai_servers")
            metric_cols = _safe_columns(conn, "ai_server_metrics")
            health_cols = _safe_columns(conn, "ai_health_scores")
            service_cols = _safe_columns(conn, "ai_service_metrics")
            if "id" not in server_cols:
                return _empty("ai_servers.id missing", database)

            metric_select = (
                ", " + _select("m", [c for c in metric_cols if c != "id"], "m_") if metric_cols else ""
            )
            health_select = (
                ", " + _select("h", [c for c in health_cols if c != "id"], "h_") if health_cols else ""
            )
            service_select = (
                ", " + _select("svc", [c for c in service_cols if c != "id"], "svc_")
                if service_cols
                else ""
            )

            sql = text(
                f"SELECT {_select('s', server_cols)}"
                + metric_select
                + health_select
                + service_select
                + """
                FROM ai_servers s
                """
                + (
                    """
                LEFT JOIN ai_server_metrics m
                  ON m.id = (
                    SELECT x.id FROM ai_server_metrics x
                    WHERE x.server_id = s.id
                    ORDER BY x.id DESC LIMIT 1
                  )
                    """
                    if metric_cols
                    else ""
                )
                + (
                    """
                LEFT JOIN ai_health_scores h
                  ON h.id = (
                    SELECT x.id FROM ai_health_scores x
                    WHERE x.server_id = s.id
                    ORDER BY x.id DESC LIMIT 1
                  )
                    """
                    if health_cols
                    else ""
                )
                + (
                    """
                LEFT JOIN ai_service_metrics svc
                  ON svc.id = (
                    SELECT x.id FROM ai_service_metrics x
                    WHERE x.server_id = s.id
                    ORDER BY x.id DESC LIMIT 1
                  )
                    """
                    if service_cols
                    else ""
                )
                + " ORDER BY s.server_name"
            )
            rows = conn.execute(sql).mappings().all()

            alerts: dict[int, int] = {}
            if _table_exists(conn, "ai_server_alerts"):
                alert_rows = conn.execute(
                    text(
                        "SELECT server_id, COUNT(*) AS n FROM ai_server_alerts "
                        "WHERE resolved = 0 OR resolved IS NULL "
                        "GROUP BY server_id"
                    )
                ).mappings().all()
                for row in alert_rows:
                    sid = _int(row.get("server_id"))
                    if sid is not None:
                        alerts[sid] = _int(row.get("n")) or 0

        servers = [_map_server(row, alerts) for row in rows]
        return {"ok": True, "database": database, "reason": None, "servers": servers}
    except Exception as exc:
        return _empty(str(exc), database)


def _map_server(row, alerts: dict[int, int]) -> dict:
    server_id = int(row["id"])
    extras = flatten_service_payload(_first(row, "svc_payload", "payload"))
    health_score = _int(_first(row, "h_overall_score", "overall_score"))
    health_status = _str(_first(row, "h_status", "status"))
    return {
        "id": server_id,
        "server_name": _str(_first(row, "server_name", "hostname")) or f"ai-{server_id}",
        "ip_address": _str(_first(row, "ip_address")) or "",
        "hostname": _str(_first(row, "hostname")),
        "group": _str(_first(row, "server_group", "group_id", "group", "server_type")),
        "server_type": _str(_first(row, "svc_server_type", "server_type")),
        "health_score": health_score,
        "health_status": health_status,
        "cpu_utilization": _num(_first(row, "m_cpu_utilization", "cpu_utilization")),
        "memory_utilization": _num(_first(row, "m_memory_utilization", "memory_utilization")),
        "storage_utilization": _num(_first(row, "m_storage_utilization", "storage_utilization")),
        "load_average": _num(_first(row, "m_load_average", "load_average")),
        "gpu_utilization": _num(_first(row, "m_gpu_utilization", "gpu_utilization")),
        "gpu_temperature": _num(_first(row, "m_gpu_temperature", "gpu_temperature")),
        "open_alerts": alerts.get(server_id, 0),
        "recorded_at": _first(row, "svc_created_at", "m_timestamp", "m_created_at", "h_created_at"),
        "extras": extras,
    }
