"""Add label and per-watch check interval on databases created before those columns."""

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)

_ADDS = (
    ("label", "ALTER TABLE process_watches ADD COLUMN label VARCHAR(128) NOT NULL DEFAULT ''"),
    (
        "check_interval",
        "ALTER TABLE process_watches ADD COLUMN check_interval INT NOT NULL DEFAULT 60",
    ),
    (
        "check_interval_unit",
        "ALTER TABLE process_watches ADD COLUMN check_interval_unit VARCHAR(16) NOT NULL DEFAULT 'seconds'",
    ),
)


def ensure_process_watch_schema() -> None:
    insp = inspect(engine)
    if not insp.has_table("process_watches"):
        return
    cols = {column["name"] for column in insp.get_columns("process_watches")}
    pending = [sql for name, sql in _ADDS if name not in cols]
    if not pending:
        return
    with engine.begin() as conn:
        for sql in pending:
            conn.execute(text(sql))
    logger.info("Added process_watches columns: %s", ", ".join(name for name, _sql in _ADDS if name not in cols))
