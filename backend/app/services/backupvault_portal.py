"""Read-only BackupVault extras from MariaDB `backupvault`.

Dashboard KPIs, incremental job status, and dump trees only.
Never SELECT password / secret / token. Never restore, query, SFTP, or start jobs.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
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
_SIZE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*([kmgtpe]i?b?)?", re.I)


def _engine():
    if not settings.legacy_metrics_database_url:
        return None, "LEGACY_METRICS_DATABASE_URL not set"
    database = settings.legacy_backupvault_database or "backupvault"
    engine = get_legacy_metrics_engine(database)
    if engine is None:
        return None, "engine unavailable"
    return engine, database


def _empty(kind: str, reason: str, database: str | None = None) -> dict:
    extra: dict[str, Any] = {"ok": False, "reason": reason, "database": database}
    if kind == "dashboard":
        extra.update(
            {
                "live_db_servers": 0,
                "today_runs": 0,
                "today_success": 0,
                "today_failed": 0,
                "failures_30d": 0,
                "primary_nfs_pct": None,
                "primary_nfs_used": None,
                "primary_nfs_size": None,
                "data_backed_up_bytes": None,
                "data_backed_up_label": None,
                "remote_used": None,
                "remote_size": None,
                "remote_pct": None,
                "s3_bytes": None,
                "s3_label": None,
                "s3_objects": None,
                "calendar": [],
                "history_14d": [],
            }
        )
    elif kind == "incremental":
        extra.update({"jobs": [], "host": None, "schedule": None, "last_cycle": None})
    elif kind == "repositories":
        extra.update({"tiers": []})
    return extra


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
        if any(hint in name.lower() for hint in _SECRET_HINTS):
            continue
        out.append(name)
    return out


def _table_exists(conn, name: str) -> bool:
    count = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl"
        ),
        {"tbl": name},
    ).scalar()
    return bool(count)


def _list_tables(conn) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME"
        )
    ).all()
    return [name for (name,) in rows if isinstance(name, str) and _IDENT.match(name)]


def _pick_table(tables: list[str], needles: tuple[str, ...], exclude: tuple[str, ...] = ()) -> str | None:
    for name in tables:
        low = name.lower()
        if any(part in low for part in exclude):
            continue
        if any(needle in low for needle in needles):
            return name
    return None


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


def _find(row, *needles: str, exclude: tuple[str, ...] = ()):
    for key, val in row.items():
        low = str(key).lower()
        if any(part in low for part in exclude):
            continue
        if any(needle in low for needle in needles):
            return val
    return None


def _as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def parse_size_bytes(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    text_val = str(value).strip().replace(",", "")
    match = _SIZE_RE.fullmatch(text_val.replace(" ", "")) or _SIZE_RE.search(text_val)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "b").lower()
    mult = {
        "b": 1,
        "k": 1000,
        "kb": 1000,
        "kib": 1024,
        "m": 1000**2,
        "mb": 1000**2,
        "mib": 1024**2,
        "g": 1000**3,
        "gb": 1000**3,
        "gib": 1024**3,
        "t": 1000**4,
        "tb": 1000**4,
        "tib": 1024**4,
    }
    return int(amount * mult.get(unit, 1))


def format_bytes(value: int | None) -> str | None:
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


def classify_dest(path: str | None = None, dest_type: str | None = None, role: str | None = None) -> str:
    hay = " ".join(part for part in (path, dest_type, role) if part).lower()
    if any(token in hay for token in ("s3", "aws", "object")):
        return "s3"
    if any(token in hay for token in ("remote", "onsite", "sftp", "dr")):
        return "remote"
    if "secondary" in hay:
        return "secondary"
    if "primary" in hay:
        return "primary"
    return "other"


def _select_rows(conn, table: str, limit: int = 400) -> list[dict]:
    cols = _safe_columns(conn, table)
    if not cols:
        return []
    quoted = ", ".join(f"`{c}`" for c in cols)
    order = "id" if "id" in cols else "ts" if "ts" in cols else cols[0]
    rows = conn.execute(
        text(f"SELECT {quoted} FROM `{table}` ORDER BY `{order}` DESC LIMIT :lim"),
        {"lim": limit},
    ).mappings().all()
    return [dict(row) for row in rows]


def fetch_backupvault_dashboard() -> dict:
    cached = get_cached("bv_dashboard")
    if cached is not None:
        return cached
    out = _fetch_dashboard()
    set_cached("bv_dashboard", out)
    return out


def _fetch_dashboard() -> dict:
    engine, extra = _engine()
    if engine is None:
        return _empty("dashboard", extra)
    database = extra
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("SET SESSION max_execution_time = 12000"))
            except Exception:
                pass
            now = conn.execute(text("SELECT NOW() AS now, CURDATE() AS today")).mappings().first()
            today = now["today"] if now else date.today()
            clock = now["now"] if now else datetime.now()
            live_db = 0
            if _table_exists(conn, "backup_targets"):
                live_db = int(
                    conn.execute(text("SELECT COUNT(*) FROM backup_targets WHERE COALESCE(is_active, 1) = 1")).scalar()
                    or 0
                )
            elif _table_exists(conn, "db_servers"):
                live_db = int(conn.execute(text("SELECT COUNT(*) FROM db_servers")).scalar() or 0)

            start_35 = datetime.combine(today, datetime.min.time()) - timedelta(days=34)
            runs: list[dict] = []
            if _table_exists(conn, "backup_runs"):
                runs = [
                    dict(row)
                    for row in conn.execute(
                        text(
                            "SELECT id, status, started_at, file_size_bytes, file_path, backup_type "
                            "FROM backup_runs WHERE started_at >= :since ORDER BY id DESC LIMIT 2000"
                        ),
                        {"since": start_35},
                    ).mappings().all()
                ]

            transfers: list[dict] = []
            if _table_exists(conn, "backup_transfers"):
                tcols = _safe_columns(conn, "backup_transfers")
                wanted = [c for c in ("run_id", "dest_type", "file_size_bytes", "bytes", "size_bytes", "object_count") if c in tcols]
                if wanted:
                    transfers = [
                        dict(row)
                        for row in conn.execute(
                            text(f"SELECT {', '.join(f'`{c}`' for c in wanted)} FROM backup_transfers LIMIT 4000")
                        ).mappings().all()
                    ]

            nfs_rows: list[dict] = []
            if _table_exists(conn, "nfs_servers"):
                nfs_cols = _safe_columns(conn, "nfs_servers")
                snap_cols = (
                    _safe_columns(conn, "nfs_monitoring_snapshots")
                    if _table_exists(conn, "nfs_monitoring_snapshots")
                    else []
                )
                nfs_select = ", ".join(f"n.`{c}` AS `{c}`" for c in nfs_cols)
                snap_select = ", ".join(f"ns.`{c}` AS `snap_{c}`" for c in snap_cols if c != "id")
                join = ""
                if snap_cols:
                    join = (
                        " LEFT JOIN nfs_monitoring_snapshots ns ON ns.id = ("
                        "SELECT x.id FROM nfs_monitoring_snapshots x "
                        "WHERE x.server_id = n.id ORDER BY x.snapshot_at DESC, x.id DESC LIMIT 1)"
                    )
                nfs_rows = [
                    dict(row)
                    for row in conn.execute(
                        text(f"SELECT {nfs_select}" + (f", {snap_select}" if snap_select else "") + f" FROM nfs_servers n{join}")
                    ).mappings().all()
                ]

        today_runs = [r for r in runs if _as_dt(r.get("started_at")) and _as_dt(r.get("started_at")).date() == today]
        today_success = sum(1 for r in today_runs if str(r.get("status") or "").lower() == "success")
        today_failed = sum(1 for r in today_runs if str(r.get("status") or "").lower() == "failed")
        cutoff_30 = datetime.combine(today, datetime.min.time()) - timedelta(days=30)
        failures_30d = sum(
            1
            for r in runs
            if str(r.get("status") or "").lower() == "failed"
            and (_as_dt(r.get("started_at")) or datetime.min) >= cutoff_30
        )

        primary = _pick_nfs(nfs_rows, "primary")
        remote = _pick_nfs(nfs_rows, "remote") or _pick_nfs(nfs_rows, "onsite")
        s3_bytes, s3_objects = _s3_totals(transfers, runs)
        backed = _int(_sum_sizes(r.get("file_size_bytes") for r in today_runs))
        if backed is None or backed == 0:
            backed = _int(_sum_sizes(r.get("file_size_bytes") for r in runs if str(r.get("status") or "").lower() == "success"))

        out = {
            "ok": True,
            "reason": None,
            "database": database,
            "checked_at": clock,
            "live_db_servers": live_db,
            "today_runs": len(today_runs),
            "today_success": today_success,
            "today_failed": today_failed,
            "failures_30d": failures_30d,
            "primary_nfs_pct": _nfs_pct(primary),
            "primary_nfs_used": _nfs_field(primary, "disk_used", "snap_disk_used"),
            "primary_nfs_size": _nfs_field(primary, "disk_size", "snap_disk_size"),
            "data_backed_up_bytes": backed,
            "data_backed_up_label": format_bytes(backed),
            "remote_used": _nfs_field(remote, "disk_used", "snap_disk_used"),
            "remote_size": _nfs_field(remote, "disk_size", "snap_disk_size"),
            "remote_pct": _nfs_pct(remote),
            "s3_bytes": s3_bytes,
            "s3_label": format_bytes(s3_bytes),
            "s3_objects": s3_objects,
            "calendar": _calendar(runs, today, 35),
            "history_14d": _daily_counts(runs, today, 14),
        }
        return out
    except Exception as exc:
        return _empty("dashboard", str(exc), database)


def _nfs_field(row: dict | None, *names: str) -> str | None:
    if not row:
        return None
    return _str(_first(row, *names))


def _nfs_pct(row: dict | None) -> float | None:
    if not row:
        return None
    direct = _num(_first(row, "snap_disk_pct", "disk_pct"))
    if direct is not None:
        return direct
    used = parse_size_bytes(_first(row, "disk_used", "snap_disk_used"))
    total = parse_size_bytes(_first(row, "disk_size", "snap_disk_size"))
    if used is not None and total:
        return round(100.0 * used / total, 1)
    return None


def _pick_nfs(rows: list[dict], needle: str) -> dict | None:
    for row in rows:
        hay = " ".join(
            str(row.get(key) or "")
            for key in ("role", "name", "export_path", "mount_point", "host")
        ).lower()
        if needle in hay:
            return row
    return rows[0] if needle == "primary" and rows else None


def _s3_totals(transfers: list[dict], runs: list[dict]) -> tuple[int | None, int | None]:
    s3 = [t for t in transfers if classify_dest(dest_type=_str(t.get("dest_type"))) == "s3"]
    if s3:
        total = _sum_sizes(t.get("file_size_bytes") or t.get("bytes") or t.get("size_bytes") for t in s3)
        objects = _sum_sizes(t.get("object_count") for t in s3 if t.get("object_count") is not None)
        return total, objects if objects else len(s3)
    s3_runs = [r for r in runs if classify_dest(path=_str(r.get("file_path"))) == "s3"]
    if s3_runs:
        return _sum_sizes(r.get("file_size_bytes") for r in s3_runs), len(s3_runs)
    return None, None


def _sum_sizes(values) -> int | None:
    nums = [parse_size_bytes(v) for v in values]
    present = [n for n in nums if n is not None]
    if not present:
        return None
    return int(sum(present))


def _calendar(runs: list[dict], today: date, days: int) -> list[dict]:
    start = today - timedelta(days=days - 1)
    buckets: dict[date, dict[str, int]] = {
        start + timedelta(days=i): {"success": 0, "failed": 0, "partial": 0, "total": 0}
        for i in range(days)
    }
    for run in runs:
        stamp = _as_dt(run.get("started_at"))
        if stamp is None:
            continue
        day = stamp.date()
        if day not in buckets:
            continue
        status = str(run.get("status") or "").lower()
        buckets[day]["total"] += 1
        if status in buckets[day]:
            buckets[day][status] += 1
    out = []
    for day in sorted(buckets):
        counts = buckets[day]
        tone = "empty"
        if counts["failed"]:
            tone = "failed"
        elif counts["partial"]:
            tone = "partial"
        elif counts["success"]:
            tone = "success"
        out.append({"date": day.isoformat(), "tone": tone, **counts})
    return out


def _daily_counts(runs: list[dict], today: date, days: int) -> list[dict]:
    start = today - timedelta(days=days - 1)
    buckets = {start + timedelta(days=i): 0 for i in range(days)}
    for run in runs:
        stamp = _as_dt(run.get("started_at"))
        if stamp is None:
            continue
        day = stamp.date()
        if day in buckets:
            buckets[day] += 1
    return [{"date": day.isoformat(), "runs": buckets[day]} for day in sorted(buckets)]


def fetch_backupvault_incremental() -> dict:
    cached = get_cached("bv_incremental")
    if cached is not None:
        return cached
    out = _fetch_incremental()
    set_cached("bv_incremental", out)
    return out


def _fetch_incremental() -> dict:
    engine, extra = _engine()
    if engine is None:
        return _empty("incremental", extra)
    database = extra
    try:
        with engine.connect() as conn:
            tables = _list_tables(conn)
            table = _pick_table(tables, ("incremental", "rsync"), exclude=("snapshot", "sync_state"))
            jobs: list[dict] = []
            host = None
            schedule = None
            last_cycle = None
            source = "none"
            if table:
                source = table
                for row in _select_rows(conn, table, 200):
                    mapped = map_incremental_row(row)
                    if mapped:
                        jobs.append(mapped)
                if jobs:
                    host = jobs[0].get("host")
                    schedule = jobs[0].get("schedule")
                    last_cycle = jobs[0].get("last_success")
            if not jobs and _table_exists(conn, "backup_runs"):
                source = "backup_runs"
                rows = conn.execute(
                    text(
                        "SELECT r.id, r.status, r.started_at, r.completed_at, r.file_size_bytes, "
                        "r.file_path, r.backup_type, t.name AS target_name, t.host AS target_host "
                        "FROM backup_runs r LEFT JOIN backup_targets t ON t.id = r.target_id "
                        "WHERE LOWER(COALESCE(r.backup_type, '')) LIKE '%inc%' "
                        "OR LOWER(COALESCE(r.backup_type, '')) LIKE '%rsync%' "
                        "ORDER BY r.id DESC LIMIT 200"
                    )
                ).mappings().all()
                latest: dict[str, dict] = {}
                for raw in rows:
                    name = _str(raw.get("target_name")) or f"run-{raw.get('id')}"
                    if name in latest:
                        continue
                    latest[name] = map_incremental_row(dict(raw), fallback_name=name)
                jobs = list(latest.values())
        return {
            "ok": True,
            "reason": None,
            "database": database,
            "source": source,
            "host": host,
            "schedule": schedule,
            "last_cycle": last_cycle,
            "jobs": jobs,
        }
    except Exception as exc:
        return _empty("incremental", str(exc), database)


def map_incremental_row(row: dict, fallback_name: str | None = None) -> dict:
    size = parse_size_bytes(
        _first(row, "file_size_bytes", "source_size", "size_bytes", "bytes")
        or _find(row, "size", "bytes")
    )
    name = _str(
        _first(row, "database_name", "db_name", "target_name", "name", "job_name")
        or _find(row, "database", "target")
    ) or fallback_name or "job"
    return {
        "id": _int(_first(row, "id")) or 0,
        "name": name,
        "script": _str(_first(row, "script", "script_name", "job_script") or _find(row, "script")),
        "status": _str(_first(row, "status", "last_status") or _find(row, "status")),
        "last_success": _as_dt(
            _first(row, "last_success", "last_run", "completed_at", "started_at")
            or _find(row, "success", "completed")
        ),
        "file_size_bytes": size,
        "file_size_label": format_bytes(size),
        "remote_path": _str(
            _first(row, "remote_path", "dest_path", "destination", "file_path")
            or _find(row, "remote", "dest")
        ),
        "host": _str(_first(row, "host", "target_host", "source_host") or _find(row, "host")),
        "schedule": _str(_first(row, "schedule", "cron") or _find(row, "schedule")),
    }


def fetch_backupvault_repositories() -> dict:
    cached = get_cached("bv_repositories")
    if cached is not None:
        return cached
    out = _fetch_repositories()
    set_cached("bv_repositories", out)
    return out


def _fetch_repositories() -> dict:
    engine, extra = _engine()
    if engine is None:
        return _empty("repositories", extra)
    database = extra
    try:
        with engine.connect() as conn:
            tables = _list_tables(conn)
            table = _pick_table(
                tables,
                ("backup_file", "repository", "dump_file", "nfs_file", "file_catalog"),
                exclude=("transfer", "snapshot", "log"),
            )
            folders: list[dict] = []
            source = "none"
            if table:
                source = table
                folders = [map_repo_folder(row) for row in _select_rows(conn, table, 800)]
            if not folders and _table_exists(conn, "backup_runs"):
                source = "backup_runs"
                dest_select = (
                    "(SELECT GROUP_CONCAT(DISTINCT x.dest_type) FROM backup_transfers x WHERE x.run_id = r.id) AS dest_types"
                    if _table_exists(conn, "backup_transfers")
                    else "NULL AS dest_types"
                )
                rows = conn.execute(
                    text(
                        "SELECT r.id, r.status, r.started_at, r.file_size_bytes, r.file_path, "
                        f"r.backup_type, t.name AS target_name, {dest_select} "
                        "FROM backup_runs r LEFT JOIN backup_targets t ON t.id = r.target_id "
                        "WHERE r.status = 'success' AND r.file_path IS NOT NULL "
                        "ORDER BY r.id DESC LIMIT 800"
                    )
                ).mappings().all()
                latest: dict[tuple[str, str], dict] = {}
                counts: dict[tuple[str, str], int] = defaultdict(int)
                for raw in rows:
                    name = _str(raw.get("target_name")) or "unknown"
                    dest = classify_dest(_str(raw.get("file_path")), _str(raw.get("dest_types")))
                    key = (dest, name)
                    counts[key] += 1
                    if key not in latest:
                        latest[key] = map_repo_folder(dict(raw), fallback_name=name, dest=dest)
                for key, folder in latest.items():
                    folder["file_count"] = counts[key]
                    folders.append(folder)
        tiers = _group_tiers(folders)
        return {"ok": True, "reason": None, "database": database, "source": source, "tiers": tiers}
    except Exception as exc:
        return _empty("repositories", str(exc), database)


def map_repo_folder(row: dict, fallback_name: str | None = None, dest: str | None = None) -> dict:
    size = parse_size_bytes(
        _first(row, "file_size_bytes", "size_bytes", "bytes", "latest_size") or _find(row, "size")
    )
    path = _str(_first(row, "file_path", "path", "latest_file") or _find(row, "file", "path"))
    name = _str(
        _first(row, "database_name", "folder", "target_name", "name") or _find(row, "database", "folder")
    ) or fallback_name or "folder"
    dest = dest or classify_dest(path, _str(_first(row, "dest_type", "dest_types", "tier", "role")))
    return {
        "name": name,
        "dest": dest,
        "latest_file": path.split("/")[-1] if path else None,
        "file_path": path,
        "file_size_bytes": size,
        "file_size_label": format_bytes(size),
        "modified_at": _as_dt(_first(row, "modified_at", "mtime", "started_at", "updated_at")),
        "file_count": _int(_first(row, "file_count", "files", "object_count")) or 1,
    }


def _group_tiers(folders: list[dict]) -> list[dict]:
    order = ("primary", "secondary", "remote", "s3", "other")
    labels = {
        "primary": "Primary DB storage",
        "secondary": "Secondary DB storage",
        "remote": "Remote onsite",
        "s3": "AWS S3",
        "other": "Other destinations",
    }
    grouped: dict[str, list[dict]] = defaultdict(list)
    for folder in folders:
        grouped[folder.get("dest") or "other"].append(folder)
    tiers = []
    for dest in order:
        items = grouped.get(dest) or []
        if not items:
            continue
        files = sum(int(item.get("file_count") or 0) for item in items)
        bytes_total = _sum_sizes(item.get("file_size_bytes") for item in items)
        tiers.append(
            {
                "id": dest,
                "label": labels[dest],
                "folder_count": len(items),
                "file_count": files,
                "bytes_label": format_bytes(bytes_total),
                "folders": items[:80],
            }
        )
    return tiers


def attach_run_logs(runs: list[dict]) -> list[dict]:
    if not runs:
        return runs
    engine, _extra = _engine()
    if engine is None:
        return runs
    try:
        with engine.connect() as conn:
            tables = _list_tables(conn)
            table = _pick_table(tables, ("run_log", "backup_log", "job_log"), exclude=("pflog",))
            if not table:
                return runs
            cols = _safe_columns(conn, table)
            run_col = next((c for c in cols if c in {"run_id", "backup_run_id", "job_id"}), None)
            body_col = next((c for c in cols if any(n in c.lower() for n in ("message", "body", "log", "text", "output"))), None)
            if not run_col or not body_col or not _IDENT.match(run_col) or not _IDENT.match(body_col):
                return runs
            ids = [row["id"] for row in runs if row.get("id") is not None][:200]
            if not ids:
                return runs
            placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
            params = {f"id{i}": rid for i, rid in enumerate(ids)}
            rows = conn.execute(
                text(
                    f"SELECT `{run_col}` AS run_id, LEFT(`{body_col}`, 400) AS excerpt "
                    f"FROM `{table}` WHERE `{run_col}` IN ({placeholders}) "
                    f"ORDER BY `{run_col}` DESC LIMIT 400"
                ),
                params,
            ).mappings().all()
            latest: dict[int, str] = {}
            for row in rows:
                rid = _int(row.get("run_id"))
                if rid is None or rid in latest:
                    continue
                latest[rid] = _str(row.get("excerpt")) or ""
        for run in runs:
            rid = run.get("id")
            if rid in latest:
                run["log_excerpt"] = latest[rid]
        return runs
    except Exception:
        return runs
