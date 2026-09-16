"""Create fleet_collect_runs and migrate legacy `trigger` column (MariaDB reserved word)."""

import logging

from sqlalchemy import inspect, text

from app.db.session import Base, engine
from app.models.fleet_collect_run import FleetCollectRun

logger = logging.getLogger(__name__)


def ensure_fleet_collect_schema() -> None:
    insp = inspect(engine)
    if not insp.has_table("fleet_collect_runs"):
        FleetCollectRun.__table__.create(bind=engine, checkfirst=True)
        logger.info("Created table fleet_collect_runs")
        return

    cols = {c["name"] for c in insp.get_columns("fleet_collect_runs")}
    if "run_trigger" in cols:
        return
    if "trigger" in cols:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE fleet_collect_runs "
                    "CHANGE COLUMN `trigger` run_trigger VARCHAR(32) NOT NULL DEFAULT 'celery'"
                )
            )
        logger.info("Renamed fleet_collect_runs.trigger -> run_trigger")
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE fleet_collect_runs "
                "ADD COLUMN run_trigger VARCHAR(32) NOT NULL DEFAULT 'celery'"
            )
        )
    logger.info("Added fleet_collect_runs.run_trigger")
