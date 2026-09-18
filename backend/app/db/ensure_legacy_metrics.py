"""Idempotent schema for legacy portal metrics sync."""

from app.db.session import Base, engine
from app.models.legacy_metric_point import LegacyMetricPoint
from app.models.legacy_sync_state import LegacySyncState


def ensure_legacy_metrics_schema() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[LegacySyncState.__table__, LegacyMetricPoint.__table__],
    )
