from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GpuInsightsSnapshotRow(Base):
    __tablename__ = "gpu_insights_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    process_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tcp_inuse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tcp_connection_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tcp_established: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listen_sockets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listen_port_8000: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listen_port_8011: Mapped[int | None] = mapped_column(Integer, nullable=True)
    localhost_ping_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cpu_util_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpu_util_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpu_temp_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_rx_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_tx_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    collect_error: Mapped[str | None] = mapped_column(Text, nullable=True)
