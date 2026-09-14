from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EmailQueueSnapshot(Base):
    __tablename__ = "email_queue_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    queue_messages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_size_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    postfix_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    collect_error: Mapped[str | None] = mapped_column(Text, nullable=True)
