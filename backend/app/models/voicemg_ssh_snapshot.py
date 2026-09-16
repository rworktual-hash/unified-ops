from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VoiceMgSshSnapshot(Base):
    __tablename__ = "voicemg_ssh_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    service_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    docker_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    nginx_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    containers_running: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_process_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    app_process_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpu_device_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpu_util_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_mount: Mapped[str | None] = mapped_column(String(512), nullable=True)
    data_disk_used_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_disk_free_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_service_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    healthcheck_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    collect_error: Mapped[str | None] = mapped_column(Text, nullable=True)
