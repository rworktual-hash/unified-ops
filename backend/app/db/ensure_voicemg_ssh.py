"""Ensure voicemg_ssh_snapshots exists on existing deployments."""

import logging

from sqlalchemy import inspect

from app.db.session import Base, engine

logger = logging.getLogger(__name__)


def ensure_voicemg_ssh_schema() -> None:
    insp = inspect(engine)
    if insp.has_table("voicemg_ssh_snapshots"):
        return
    from app.models import voicemg_ssh_snapshot as _model  # noqa: F401

    Base.metadata.create_all(bind=engine, tables=[_model.VoiceMgSshSnapshot.__table__])
    logger.info("Created voicemg_ssh_snapshots table")
