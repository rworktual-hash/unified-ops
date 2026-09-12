from typing import Literal

from pydantic import BaseModel, Field

SshAuthMode = Literal["auto", "key", "password"]


class ServerCreate(BaseModel):
    server_name: str = Field(..., min_length=1, max_length=255)
    ip_address: str = Field(..., min_length=1, max_length=45)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(..., min_length=1, max_length=128)
    credential_ref: str | None = Field(default=None, max_length=128)
    ssh_password: str | None = Field(default=None, max_length=512)
    ssh_auth_mode: SshAuthMode = "auto"
    server_type: str | None = Field(default=None, max_length=64)
    project: str | None = Field(default=None, max_length=64)
    is_active: bool = True


class ServerUpdate(BaseModel):
    server_name: str | None = Field(default=None, min_length=1, max_length=255)
    ip_address: str | None = Field(default=None, min_length=1, max_length=45)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_username: str | None = Field(default=None, min_length=1, max_length=128)
    credential_ref: str | None = Field(default=None, max_length=128)
    ssh_password: str | None = Field(default=None, max_length=512)
    ssh_auth_mode: SshAuthMode | None = None
    server_type: str | None = Field(default=None, max_length=64)
    project: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class ServerRead(BaseModel):
    id: int
    server_name: str
    ip_address: str
    ssh_port: int
    ssh_username: str
    credential_ref: str | None
    ssh_auth_mode: str
    has_ssh_password: bool
    server_type: str | None
    project: str | None
    is_active: bool

    model_config = {"from_attributes": True}


def server_to_read(server) -> ServerRead:
    return ServerRead(
        id=server.id,
        server_name=server.server_name,
        ip_address=server.ip_address,
        ssh_port=server.ssh_port,
        ssh_username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
        has_ssh_password=bool(server.ssh_password),
        server_type=server.server_type,
        project=server.project,
        is_active=server.is_active,
    )
