from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EmailSshSnapshot(Base):
    """Read-only SSH collect: queue, services, pflogsumm-style day stats."""

    __tablename__ = "email_ssh_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    queue_messages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_size_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_active: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_deferred: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_hold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    postfix_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dovecot_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    opendkim_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    amavis_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    clamav_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mail_received: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mail_delivered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mail_bounced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mail_rejected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mail_deferred: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_reject_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_bounce_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_amavis_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_spam_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fail2ban_banned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recent_log_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    collect_error: Mapped[str | None] = mapped_column(Text, nullable=True)
