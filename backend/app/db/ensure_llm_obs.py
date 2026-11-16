"""Add columns on databases created before per-customer agent traces."""

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)

_TRACE_ADDS = (
    ("session_id", "ALTER TABLE llm_obs_traces ADD COLUMN session_id VARCHAR(200) NULL"),
    ("customer", "ALTER TABLE llm_obs_traces ADD COLUMN customer VARCHAR(128) NOT NULL DEFAULT ''"),
    ("customer_role", "ALTER TABLE llm_obs_traces ADD COLUMN customer_role VARCHAR(32) NOT NULL DEFAULT ''"),
    ("agent_name", "ALTER TABLE llm_obs_traces ADD COLUMN agent_name VARCHAR(128) NOT NULL DEFAULT ''"),
    ("agent_mode", "ALTER TABLE llm_obs_traces ADD COLUMN agent_mode VARCHAR(32) NOT NULL DEFAULT ''"),
)

_RUN_ADDS = (
    ("tool_source", "ALTER TABLE llm_obs_runs ADD COLUMN tool_source VARCHAR(16) NOT NULL DEFAULT ''"),
    ("connector", "ALTER TABLE llm_obs_runs ADD COLUMN connector VARCHAR(128) NOT NULL DEFAULT ''"),
)


def ensure_llm_obs_schema() -> None:
    insp = inspect(engine)
    pending: list[tuple[str, str]] = []
    if insp.has_table("llm_obs_traces"):
        cols = {column["name"] for column in insp.get_columns("llm_obs_traces")}
        pending.extend((name, sql) for name, sql in _TRACE_ADDS if name not in cols)
    if insp.has_table("llm_obs_runs"):
        cols = {column["name"] for column in insp.get_columns("llm_obs_runs")}
        pending.extend((name, sql) for name, sql in _RUN_ADDS if name not in cols)
    if not pending:
        return
    with engine.begin() as conn:
        for _name, sql in pending:
            conn.execute(text(sql))
    logger.info("Added llm observability columns: %s", ", ".join(name for name, _sql in pending))
