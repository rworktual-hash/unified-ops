from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BackupVaultSshSnapshot(Base):
    __tablename__ = "backupvault_ssh_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    service_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    docker_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    nginx_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cron_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    containers_running: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    replication_io_running: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    replication_sql_running: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    replica_in_recovery: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    replication_lag_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    db_connections: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slow_queries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    db_uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_mount: Mapped[str | None] = mapped_column(String(512), nullable=True)
    data_disk_used_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_disk_free_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_backup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_backup_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    latest_backup_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    backup_file_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    backup_total_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    backup_process_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_service_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    healthcheck_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    collect_error: Mapped[str | None] = mapped_column(Text, nullable=True)
