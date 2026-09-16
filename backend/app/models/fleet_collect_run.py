from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FleetCollectRun(Base):
    __tablename__ = "fleet_collect_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    servers_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    servers_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="celery")
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
