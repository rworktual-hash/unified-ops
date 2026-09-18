from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LegacyMetricPoint(Base):
    __tablename__ = "legacy_metric_points"
    __table_args__ = (
        UniqueConstraint("domain", "source_id", "metric_key", name="uq_legacy_metric_point"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    server_id: Mapped[int | None] = mapped_column(ForeignKey("servers.id"), nullable=True, index=True)
    host_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metric_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_value_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
