"""Add columns to backupvault_ssh_snapshots on existing deployments."""

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)

_NEW_COLS = [
    ("backup_file_count", "INTEGER NULL"),
    ("backup_total_size_bytes", "BIGINT NULL"),
    ("extra_service_status", "TEXT NULL"),
    ("healthcheck_status", "TEXT NULL"),
]


def ensure_backupvault_ssh_schema() -> None:
    insp = inspect(engine)
    if not insp.has_table("backupvault_ssh_snapshots"):
        return
    existing = {c["name"] for c in insp.get_columns("backupvault_ssh_snapshots")}
    with engine.begin() as conn:
        for name, ddl in _NEW_COLS:
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE backupvault_ssh_snapshots ADD COLUMN {name} {ddl}"))
            logger.info("Added backupvault_ssh_snapshots.%s", name)
