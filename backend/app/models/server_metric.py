from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ServerMetric(Base):
    __tablename__ = "server_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    load_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_15m: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_total_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mem_used_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mem_used_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_root_used_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_root_total_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_root_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    collect_error: Mapped[str | None] = mapped_column(Text, nullable=True)
