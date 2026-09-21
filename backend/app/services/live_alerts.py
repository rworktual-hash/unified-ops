"""Read-only open alerts from MariaDB .222 `ai_server_alerts`.

Match IP then hostname to Unified Ops inventory. Never writes .222.
Investigate runs on the matched host only.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.services.ai_insights_portal import (
    _engine,
    _first,
    _int,
    _safe_columns,
    _select,
    _str,
    _table_exists,
)
from app.services.live_cache import get_cached, set_cached


def _empty(reason: str, database: str | None = None) -> dict:
    return {"ok": False, "reason": reason, "database": database, "alerts": []}


def match_inventory_host(
    ip_address: str | None,
    hostname: str | None,
    server_name: str | None,
    inventory: list[dict],
) -> dict | None:
    ip = (ip_address or "").strip()
    if ip:
        for row in inventory:
            if (row.get("ip_address") or "").strip() == ip:
                return row
    needles = [(value or "").strip().lower() for value in (hostname, server_name) if value]
    for needle in needles:
        if not needle:
            continue
        for row in inventory:
            names = [
                (row.get("server_name") or "").strip().lower(),
                (row.get("hostname") or "").strip().lower(),
            ]
            if needle in names:
                return row
    return None


def _severity(raw: Any) -> str:
    text_val = (str(raw or "")).strip().lower()
    if text_val in {"critical", "crit", "error", "fatal", "high"}:
        return "critical"
    if text_val in {"warning", "warn", "medium"}:
        return "warning"
    if text_val in {"info", "low", "ok"}:
        return "info"
    return "warning"


def map_alert_row(row: dict) -> dict:
    source_id = _int(_first(row, "id", "alert_id")) or 0
    title = _str(_first(row, "title", "alert_title", "name", "alert_name", "summary")) or "Portal alert"
    message = _str(
        _first(row, "message", "description", "detail", "details", "reason", "alert_message")
    ) or title
    alert_type = _str(_first(row, "alert_type", "type", "category", "metric_key")) or "ai_insights"
    ip_address = _str(_first(row, "s_ip_address", "ip_address"))
    hostname = _str(_first(row, "s_hostname", "hostname"))
    portal_name = _str(_first(row, "s_server_name", "server_name")) or hostname
    return {
        "source_id": source_id,
        "source": "ai_insights",
        "alert_type": alert_type,
        "severity": _severity(_first(row, "severity", "level", "priority")),
        "status": "open",
        "title": title,
        "message": message,
        "ip_address": ip_address or "",
        "hostname": hostname,
        "portal_server_name": portal_name,
        "first_seen_at": _first(row, "created_at", "first_seen_at", "timestamp", "ts"),
        "last_seen_at": _first(row, "updated_at", "last_seen_at", "created_at", "timestamp", "ts"),
        "inventory_server_id": None,
        "inventory_server_name": None,
        "matched": False,
    }


def attach_inventory(alerts: list[dict], inventory: list[dict]) -> list[dict]:
    out = []
    for alert in alerts:
        hit = match_inventory_host(
            alert.get("ip_address"),
            alert.get("hostname"),
            alert.get("portal_server_name"),
            inventory,
        )
        row = dict(alert)
        if hit:
            row["inventory_server_id"] = hit.get("id")
            row["inventory_server_name"] = hit.get("server_name")
            row["ip_address"] = hit.get("ip_address") or row.get("ip_address") or ""
            row["matched"] = True
        out.append(row)
    return out


def fetch_ai_insights_alerts() -> dict:
    cached = get_cached("ai_insights_alerts")
    if cached is not None:
        return cached
    out = _fetch_ai_insights_alerts()
    set_cached("ai_insights_alerts", out)
    return out


def _fetch_ai_insights_alerts() -> dict:
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
            if not _table_exists(conn, "ai_server_alerts") or not _table_exists(conn, "ai_servers"):
                return _empty("ai_server_alerts or ai_servers not found", database)
            alert_cols = _safe_columns(conn, "ai_server_alerts")
            server_cols = _safe_columns(conn, "ai_servers")
            if "id" not in alert_cols or "server_id" not in alert_cols:
                return _empty("ai_server_alerts.id/server_id missing", database)
            where = "1=1"
            if "resolved" in alert_cols:
                where = "(a.`resolved` = 0 OR a.`resolved` IS NULL)"
            elif "status" in alert_cols:
                where = "LOWER(IFNULL(a.`status`,'')) NOT IN ('resolved','closed','ok')"
            sql = text(
                f"SELECT {_select('a', alert_cols)}, {_select('s', server_cols, 's_')} "
                "FROM ai_server_alerts a "
                "JOIN ai_servers s ON s.id = a.server_id "
                f"WHERE {where} "
                "ORDER BY a.id DESC LIMIT 80"
            )
            rows = conn.execute(sql).mappings().all()
        alerts = [map_alert_row(dict(row)) for row in rows if _int(_first(dict(row), "id", "alert_id"))]
        return {"ok": True, "reason": None, "database": database, "alerts": alerts}
    except Exception as exc:
        return _empty(str(exc)[:240], database)
