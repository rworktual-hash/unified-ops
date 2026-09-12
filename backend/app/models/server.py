from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    ssh_username: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ssh_password: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ssh_auth_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    server_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
