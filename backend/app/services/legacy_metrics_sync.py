from __future__ import annotations

"""
Guardrails: legacy portal MySQL on server-management (10.180.1.222) is read-only.
Only SELECT by incremental id; copies rows into unified_ops `legacy_metric_points`.
Configure table/column names after running scripts/inspect-legacy-metrics-db.py.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.legacy_metrics_session import get_legacy_metrics_engine
from app.models.legacy_metric_point import LegacyMetricPoint
from app.models.legacy_sync_state import LegacySyncState
from app.models.server import Server

DOMAIN_PROJECTS: dict[str, tuple[str, ...]] = {
    "ai_insights": ("ai", "gpu"),
    "backupvault": ("backupvault",),
    "voicemg": ("voicemg",),
    "infrastructure": ("infrastructure", "infra"),
}


@dataclass(frozen=True)
class LegacyStreamConfig:
    domain: str
    enabled: bool
    database: str | None
    table: str
    col_id: str
    col_time: str
    col_host: str
    metric_cols: tuple[str, ...]


def _stream_configs() -> list[LegacyStreamConfig]:
    return [
        LegacyStreamConfig(
            domain="ai_insights",
            enabled=settings.legacy_ai_insights_sync_enabled,
            database=settings.legacy_ai_insights_database,
            table=settings.legacy_ai_insights_table,
            col_id=settings.legacy_ai_insights_col_id,
            col_time=settings.legacy_ai_insights_col_time,
            col_host=settings.legacy_ai_insights_col_host,
            metric_cols=tuple(settings.legacy_ai_insights_metric_cols_list),
        ),
        LegacyStreamConfig(
            domain="backupvault",
            enabled=settings.legacy_backupvault_sync_enabled,
            database=settings.legacy_backupvault_database,
            table=settings.legacy_backupvault_table,
            col_id=settings.legacy_backupvault_col_id,
            col_time=settings.legacy_backupvault_col_time,
            col_host=settings.legacy_backupvault_col_host,
            metric_cols=tuple(settings.legacy_backupvault_metric_cols_list),
        ),
        LegacyStreamConfig(
            domain="voicemg",
            enabled=settings.legacy_voicemg_sync_enabled,
            database=settings.legacy_voicemg_database,
            table=settings.legacy_voicemg_table,
            col_id=settings.legacy_voicemg_col_id,
            col_time=settings.legacy_voicemg_col_time,
            col_host=settings.legacy_voicemg_col_host,
            metric_cols=tuple(settings.legacy_voicemg_metric_cols_list),
        ),
        LegacyStreamConfig(
            domain="infrastructure",
            enabled=settings.legacy_infrastructure_sync_enabled,
            database=settings.legacy_infrastructure_database,
            table=settings.legacy_infrastructure_table,
            col_id=settings.legacy_infrastructure_col_id,
            col_time=settings.legacy_infrastructure_col_time,
            col_host=settings.legacy_infrastructure_col_host,
            metric_cols=tuple(settings.legacy_infrastructure_metric_cols_list),
        ),
    ]


def _default_database_from_url() -> str | None:
    url = settings.legacy_metrics_database_url
    if not url:
        return None
    path = urlparse(url).path.strip("/")
    return path or None


def _resolve_database(stream: LegacyStreamConfig) -> str | None:
    return stream.database or _default_database_from_url()


def _stream_key(domain: str) -> str:
    return f"legacy_{domain}"


def _parse_remote_time(value: Any) -> datetime:
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


def _metric_value(raw: Any) -> tuple[float | None, str | None]:
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), None
    text_val = str(raw).strip()
    if not text_val:
        return None, None
    try:
        return float(text_val), None
    except ValueError:
        return None, text_val


def _resolve_server_id(db: Session, *, domain: str, host_value: str | None) -> int | None:
    projects = DOMAIN_PROJECTS.get(domain, ())
    query = db.query(Server).filter(Server.is_active.is_(True))
    if projects:
        query = query.filter(Server.project.in_(projects))

    if host_value:
        host_value = host_value.strip()
        name = settings.legacy_metrics_host_map.get(host_value)
        if name:
            row = query.filter(Server.server_name == name).first()
            if row:
                return row.id
        row = query.filter(Server.ip_address == host_value).first()
        if row:
            return row.id
        row = query.filter(Server.server_name == host_value).first()
        if row:
            return row.id

    default_name = settings.legacy_metrics_default_server_name
    if default_name:
        row = db.query(Server).filter(Server.server_name == default_name).first()
        if row:
            return row.id
    return None


def _get_or_create_state(db: Session, domain: str) -> LegacySyncState:
    key = _stream_key(domain)
    state = db.query(LegacySyncState).filter(LegacySyncState.stream_key == key).first()
    if state is None:
        state = LegacySyncState(stream_key=key, last_source_id=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def test_legacy_connection() -> dict:
    if not settings.legacy_metrics_database_url:
        return {"ok": False, "configured": False, "reason": "LEGACY_METRICS_DATABASE_URL not set"}
    engine = get_legacy_metrics_engine("information_schema")
    if engine is None:
        return {"ok": False, "configured": True, "reason": "Could not create engine"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "configured": True}
    except Exception as exc:
        return {"ok": False, "configured": True, "error": str(exc)}


def discover_legacy_schema() -> dict:
    probe = test_legacy_connection()
    if not probe.get("ok"):
        return {"ok": False, **probe}

    engine = get_legacy_metrics_engine("information_schema")
    assert engine is not None
    databases: list[dict] = []
    try:
        with engine.connect() as conn:
            db_rows = conn.execute(
                text(
                    "SELECT SCHEMA_NAME FROM SCHEMATA "
                    "WHERE SCHEMA_NAME NOT IN ('information_schema','mysql','performance_schema','sys') "
                    "ORDER BY SCHEMA_NAME"
                )
            ).mappings().all()
            for db_row in db_rows:
                db_name = db_row["SCHEMA_NAME"]
                table_rows = conn.execute(
                    text(
                        "SELECT TABLE_NAME FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA = :db AND TABLE_TYPE = 'BASE TABLE' "
                        "ORDER BY TABLE_NAME"
                    ),
                    {"db": db_name},
                ).mappings().all()
                tables: list[dict] = []
                for table_row in table_rows:
                    table_name = table_row["TABLE_NAME"]
                    cols = conn.execute(
                        text(
                            "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                            "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl "
                            "ORDER BY ORDINAL_POSITION"
                        ),
                        {"db": db_name, "tbl": table_name},
                    ).mappings().all()
                    count_row = conn.execute(
                        text(f"SELECT COUNT(*) AS n FROM `{db_name}`.`{table_name}`")
                    ).mappings().one()
                    tables.append(
                        {
                            "name": table_name,
                            "row_count": int(count_row["n"]),
                            "columns": [f"{c['COLUMN_NAME']} ({c['DATA_TYPE']})" for c in cols],
                        }
                    )
                databases.append({"name": db_name, "tables": tables})
        return {"ok": True, "configured": True, "databases": databases}
    except Exception as exc:
        return {"ok": False, "configured": True, "error": str(exc)}


def sync_legacy_stream(db: Session, stream: LegacyStreamConfig) -> dict:
    if not stream.enabled:
        return {"ok": True, "skipped": True, "reason": "stream disabled", "domain": stream.domain}
    if not settings.legacy_metrics_database_url:
        return {"ok": False, "skipped": True, "reason": "LEGACY_METRICS_DATABASE_URL not set", "domain": stream.domain}
    if not stream.metric_cols:
        return {"ok": False, "skipped": True, "reason": "no metric columns configured", "domain": stream.domain}

    database = _resolve_database(stream)
    if not database:
        return {
            "ok": False,
            "skipped": True,
            "reason": "set LEGACY_*_DATABASE or database in LEGACY_METRICS_DATABASE_URL",
            "domain": stream.domain,
        }

    engine = get_legacy_metrics_engine(database)
    if engine is None:
        return {"ok": False, "skipped": True, "reason": "engine unavailable", "domain": stream.domain}

    state = _get_or_create_state(db, stream.domain)
    cols = [stream.col_id, stream.col_time, stream.col_host, *stream.metric_cols]
    col_list = ", ".join(f"`{c}`" for c in cols)
    sql = text(
        f"SELECT {col_list} FROM `{stream.table}` "
        f"WHERE `{stream.col_id}` > :last_id "
        f"ORDER BY `{stream.col_id}` ASC LIMIT :lim"
    )
    params = {"last_id": state.last_source_id, "lim": settings.legacy_metrics_sync_batch_size}

    inserted = 0
    now = datetime.now(timezone.utc)
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().all()

        max_id = state.last_source_id
        for row in rows:
            source_id = int(row[stream.col_id])
            max_id = max(max_id, source_id)
            host_val = row.get(stream.col_host)
            host_key = str(host_val).strip() if host_val is not None else None
            server_id = _resolve_server_id(db, domain=stream.domain, host_value=host_key)
            recorded_at = _parse_remote_time(row.get(stream.col_time))
            for metric_key in stream.metric_cols:
                num, text_val = _metric_value(row.get(metric_key))
                if num is None and text_val is None:
                    continue
                exists = (
                    db.query(LegacyMetricPoint.id)
                    .filter(
                        LegacyMetricPoint.domain == stream.domain,
                        LegacyMetricPoint.source_id == source_id,
                        LegacyMetricPoint.metric_key == metric_key,
                    )
                    .first()
                )
                if exists:
                    continue
                db.add(
                    LegacyMetricPoint(
                        domain=stream.domain,
                        source_id=source_id,
                        server_id=server_id,
                        host_key=host_key,
                        metric_key=metric_key,
                        metric_value_num=num,
                        metric_value_text=text_val,
                        recorded_at=recorded_at,
                        synced_at=now,
                    )
                )
                inserted += 1

        state.last_source_id = max_id
        state.last_synced_at = now
        state.last_error = None
        db.commit()
        return {
            "ok": True,
            "domain": stream.domain,
            "inserted": inserted,
            "last_source_id": max_id,
            "database": database,
            "table": stream.table,
        }
    except Exception as exc:
        db.rollback()
        state.last_error = str(exc)[:500]
        db.commit()
        return {"ok": False, "domain": stream.domain, "error": str(exc), "inserted": inserted}


def sync_all_legacy_streams(db: Session, *, domain: str | None = None) -> dict:
    results: list[dict] = []
    for stream in _stream_configs():
        if domain and stream.domain != domain:
            continue
        results.append(sync_legacy_stream(db, stream))
    ok = all(r.get("ok") or r.get("skipped") for r in results)
    return {"ok": ok, "results": results}


def legacy_sync_status(db: Session) -> dict:
    configured = bool(settings.legacy_metrics_database_url)
    connection = test_legacy_connection() if configured else {"ok": False, "configured": False}
    streams: list[dict] = []
    for stream in _stream_configs():
        state = db.query(LegacySyncState).filter(LegacySyncState.stream_key == _stream_key(stream.domain)).first()
        row_count = db.query(LegacyMetricPoint).filter(LegacyMetricPoint.domain == stream.domain).count()
        streams.append(
            {
                "domain": stream.domain,
                "enabled": stream.enabled,
                "configured": bool(stream.database or _default_database_from_url()) and bool(stream.table),
                "database": _resolve_database(stream),
                "table": stream.table,
                "metric_cols": list(stream.metric_cols),
                "row_count": row_count,
                "last_source_id": state.last_source_id if state else 0,
                "last_synced_at": state.last_synced_at if state else None,
                "last_error": state.last_error if state else None,
            }
        )
    return {
        "configured": configured,
        "connection_ok": bool(connection.get("ok")),
        "connection_error": connection.get("error") or connection.get("reason"),
        "scheduled_sync_enabled": bool(
            settings.legacy_metrics_scheduled_sync_enabled and settings.legacy_metrics_database_url
        ),
        "streams": streams,
    }


def compute_legacy_overview(db: Session, *, domain: str, hours: int = 24) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        db.query(LegacyMetricPoint)
        .filter(LegacyMetricPoint.domain == domain, LegacyMetricPoint.recorded_at >= since)
        .all()
    )
    servers = {s.id: s for s in db.query(Server).filter(Server.is_active.is_(True)).all()}
    by_server: dict[int | None, list[LegacyMetricPoint]] = {}
    for row in rows:
        by_server.setdefault(row.server_id, []).append(row)

    status_counts: dict[str, int] = {}
    numeric_avgs: dict[str, list[float]] = {}
    for row in rows:
        if row.metric_value_text:
            key = row.metric_key
            val = row.metric_value_text.lower()
            status_counts[val] = status_counts.get(val, 0) + 1
        if row.metric_value_num is not None:
            numeric_avgs.setdefault(row.metric_key, []).append(row.metric_value_num)

    latest_by_server: list[dict] = []
    for server_id, points in by_server.items():
        if server_id is None:
            host = points[0].host_key if points else None
            name = host or "Unmapped"
            ip = host
        else:
            srv = servers.get(server_id)
            name = srv.server_name if srv else f"server-{server_id}"
            ip = srv.ip_address if srv else None
        latest_at = max(p.recorded_at for p in points)
        metrics: dict[str, float | str | None] = {}
        for p in sorted(points, key=lambda x: x.recorded_at, reverse=True):
            if p.metric_key not in metrics:
                metrics[p.metric_key] = p.metric_value_num if p.metric_value_num is not None else p.metric_value_text
        latest_by_server.append(
            {
                "server_id": server_id,
                "server_name": name,
                "ip_address": ip,
                "latest_at": latest_at,
                "metrics": metrics,
            }
        )
    latest_by_server.sort(key=lambda x: x["server_name"])

    averages = {
        key: round(sum(vals) / len(vals), 2)
        for key, vals in numeric_avgs.items()
        if vals
    }
    return {
        "domain": domain,
        "period_hours": hours,
        "point_count": len(rows),
        "distinct_hosts": len(by_server),
        "status_counts": status_counts,
        "averages": averages,
        "latest_by_server": latest_by_server[:100],
    }


def _format_bytes(value: int | None) -> str | None:
    if value is None:
        return None
    amount = float(value)
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while amount >= 1024 and index < len(units) - 1:
        amount /= 1024
        index += 1
    digits = 2 if index > 2 else 1
    return f"{amount:.{digits}f} {units[index]}"


def fetch_backupvault_run_history() -> dict:
    """Read-only Run History from BackupVault portal MariaDB (all jobs, not 24h)."""
    if not settings.legacy_metrics_database_url:
        return {"ok": False, "reason": "LEGACY_METRICS_DATABASE_URL not set", "runs": []}
    database = settings.legacy_backupvault_database or "backupvault"
    engine = get_legacy_metrics_engine(database)
    if engine is None:
        return {"ok": False, "reason": "engine unavailable", "runs": []}

    sql = text(
        """
        SELECT
          r.id,
          r.target_id,
          t.name AS target_name,
          t.db_type,
          t.host AS target_host,
          r.backup_type,
          r.trigger_type,
          r.status,
          r.started_at,
          r.completed_at,
          r.file_size_bytes,
          r.file_path,
          r.error_message,
          TIMESTAMPDIFF(SECOND, r.started_at, r.completed_at) AS duration_seconds,
          (SELECT COUNT(*) FROM backup_transfers x WHERE x.run_id = r.id) AS destination_count,
          (SELECT GROUP_CONCAT(DISTINCT x.dest_type SEPARATOR ',') FROM backup_transfers x WHERE x.run_id = r.id) AS dest_types
        FROM backup_runs r
        LEFT JOIN backup_targets t ON t.id = r.target_id
        ORDER BY r.id DESC
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql).mappings().all()
        runs: list[dict] = []
        counts = {"success": 0, "failed": 0, "partial": 0, "running": 0, "pending": 0}
        for row in rows:
            status = str(row.get("status") or "").lower()
            if status in counts:
                counts[status] += 1
            started = row.get("started_at")
            completed = row.get("completed_at")
            size = row.get("file_size_bytes")
            size_int = int(size) if size is not None else None
            duration = row.get("duration_seconds")
            runs.append(
                {
                    "id": int(row["id"]),
                    "target_id": int(row["target_id"]) if row.get("target_id") is not None else None,
                    "target_name": row.get("target_name") or f"target-{row.get('target_id')}",
                    "db_type": row.get("db_type"),
                    "target_host": row.get("target_host"),
                    "backup_type": row.get("backup_type"),
                    "trigger_type": row.get("trigger_type"),
                    "status": status or None,
                    "started_at": started,
                    "completed_at": completed,
                    "file_size_bytes": size_int,
                    "file_size_label": _format_bytes(size_int),
                    "file_path": row.get("file_path"),
                    "error_message": row.get("error_message"),
                    "duration_seconds": int(duration) if duration is not None else None,
                    "destination_count": int(row.get("destination_count") or 0),
                    "dest_types": row.get("dest_types"),
                }
            )
        total = len(runs)
        success_rate = round((counts["success"] / total) * 100) if total else 0
        return {
            "ok": True,
            "source": "legacy_readonly",
            "database": database,
            "total": total,
            "success_rate": success_rate,
            **counts,
            "runs": runs,
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "runs": []}


def _backupvault_engine():
    if not settings.legacy_metrics_database_url:
        return None, "LEGACY_METRICS_DATABASE_URL not set"
    database = settings.legacy_backupvault_database or "backupvault"
    engine = get_legacy_metrics_engine(database)
    if engine is None:
        return None, "engine unavailable"
    return engine, database


def fetch_backupvault_targets() -> dict:
    """Read-only backup_targets (no passwords)."""
    engine, extra = _backupvault_engine()
    if engine is None:
        return {"ok": False, "reason": extra, "targets": []}
    database = extra
    sql = text(
        """
        SELECT
          t.id,
          t.name,
          t.db_type,
          t.host,
          t.port,
          t.database_name,
          t.description,
          t.is_active,
          (
            SELECT r.status FROM backup_runs r
            WHERE r.target_id = t.id
            ORDER BY r.id DESC LIMIT 1
          ) AS last_status,
          (
            SELECT r.started_at FROM backup_runs r
            WHERE r.target_id = t.id
            ORDER BY r.id DESC LIMIT 1
          ) AS last_started_at
        FROM backup_targets t
        ORDER BY t.db_type, t.name
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql).mappings().all()
        targets = []
        for row in rows:
            targets.append(
                {
                    "id": int(row["id"]),
                    "name": row.get("name") or f"target-{row['id']}",
                    "db_type": row.get("db_type"),
                    "host": row.get("host"),
                    "port": int(row["port"]) if row.get("port") is not None else None,
                    "database_name": row.get("database_name"),
                    "description": row.get("description"),
                    "is_active": bool(row.get("is_active")) if row.get("is_active") is not None else True,
                    "last_status": str(row["last_status"]).lower() if row.get("last_status") else None,
                    "last_started_at": row.get("last_started_at"),
                }
            )
        return {"ok": True, "database": database, "targets": targets}
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "targets": []}


def fetch_backupvault_nfs() -> dict:
    engine, extra = _backupvault_engine()
    if engine is None:
        return {"ok": False, "reason": extra, "servers": []}
    database = extra
    sql = text(
        """
        SELECT id, name, host, export_path, mount_point, description, role,
               is_active, status, disk_size, disk_used, disk_avail
        FROM nfs_servers
        ORDER BY name
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql).mappings().all()
        servers = [
            {
                "id": int(row["id"]),
                "name": row.get("name") or f"nfs-{row['id']}",
                "host": row.get("host"),
                "export_path": row.get("export_path"),
                "mount_point": row.get("mount_point"),
                "description": row.get("description"),
                "role": row.get("role"),
                "is_active": bool(row.get("is_active")) if row.get("is_active") is not None else True,
                "status": row.get("status"),
                "disk_size": row.get("disk_size"),
                "disk_used": row.get("disk_used"),
                "disk_avail": row.get("disk_avail"),
            }
            for row in rows
        ]
        return {"ok": True, "database": database, "servers": servers}
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "servers": []}


def remote_table_exists(stream: LegacyStreamConfig) -> bool | None:
    database = _resolve_database(stream)
    if not database or not settings.legacy_metrics_database_url:
        return None
    engine = get_legacy_metrics_engine(database)
    if engine is None:
        return None
    try:
        insp = inspect(engine)
        return stream.table in insp.get_table_names()
    except Exception:
        return None
