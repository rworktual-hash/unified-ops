from pydantic import BaseModel, Field


class ServerCreate(BaseModel):
    server_name: str = Field(..., min_length=1, max_length=255)
    ip_address: str = Field(..., min_length=1, max_length=45)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(..., min_length=1, max_length=128)
    credential_ref: str | None = Field(default=None, max_length=128)
    server_type: str | None = Field(default=None, max_length=64)
    project: str | None = Field(default=None, max_length=64)
    is_active: bool = True


class ServerUpdate(BaseModel):
    server_name: str | None = Field(default=None, min_length=1, max_length=255)
    ip_address: str | None = Field(default=None, min_length=1, max_length=45)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_username: str | None = Field(default=None, min_length=1, max_length=128)
    credential_ref: str | None = Field(default=None, max_length=128)
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
    server_type: str | None
    project: str | None
    is_active: bool

    model_config = {"from_attributes": True}
