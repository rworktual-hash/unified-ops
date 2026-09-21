from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GpuProductSnapshotRow(Base):
    __tablename__ = "gpu_product_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    compute_process_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compute_mem_used_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    compute_process_names: Mapped[str | None] = mapped_column(String(512), nullable=True)
    docker_containers_running: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docker_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    docker_container_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_tail: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpu_model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    driver_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    collect_error: Mapped[str | None] = mapped_column(Text, nullable=True)
