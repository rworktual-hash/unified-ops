"""Add columns to email_ssh_snapshots on existing deployments."""

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)

_NEW_COLS = [
    ("queue_active", "INTEGER NULL"),
    ("queue_deferred", "INTEGER NULL"),
    ("queue_hold", "INTEGER NULL"),
    ("amavis_active", "BOOLEAN NULL"),
    ("clamav_active", "BOOLEAN NULL"),
    ("log_reject_lines", "INTEGER NULL"),
    ("log_bounce_lines", "INTEGER NULL"),
    ("log_amavis_lines", "INTEGER NULL"),
    ("log_spam_lines", "INTEGER NULL"),
    ("fail2ban_banned", "INTEGER NULL"),
]


def ensure_email_ssh_schema() -> None:
    insp = inspect(engine)
    if not insp.has_table("email_ssh_snapshots"):
        return
    existing = {c["name"] for c in insp.get_columns("email_ssh_snapshots")}
    with engine.begin() as conn:
        for name, ddl in _NEW_COLS:
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE email_ssh_snapshots ADD COLUMN {name} {ddl}"))
            logger.info("Added email_ssh_snapshots.%s", name)
