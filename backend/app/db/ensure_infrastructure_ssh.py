"""Ensure infrastructure_ssh_snapshots exists on existing deployments."""

import logging

from sqlalchemy import inspect

from app.db.session import Base, engine

logger = logging.getLogger(__name__)


def ensure_infrastructure_ssh_schema() -> None:
    insp = inspect(engine)
    if insp.has_table("infrastructure_ssh_snapshots"):
        return
    from app.models import infrastructure_ssh_snapshot as _model  # noqa: F401

    Base.metadata.create_all(bind=engine, tables=[_model.InfrastructureSshSnapshot.__table__])
    logger.info("Created infrastructure_ssh_snapshots table")
