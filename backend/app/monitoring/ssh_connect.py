"""SSH connect with key, password, or auto (key then password)."""

from __future__ import annotations

import socket

import paramiko

from app.config import settings
from app.monitoring.ssh_policy import configure_paramiko_client
from app.services.credentials import CredentialError, resolve_private_key_path

AUTH_MODES = frozenset({"auto", "key", "password"})


def connect_ssh_client(
    client: paramiko.SSHClient,
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> None:
    mode = (ssh_auth_mode or "auto").strip().lower()
    if mode not in AUTH_MODES:
        raise CredentialError(f"Invalid ssh_auth_mode '{ssh_auth_mode}'.")

    configure_paramiko_client(client)
    base = dict(
        hostname=host,
        port=port,
        username=username,
        timeout=settings.ssh_connect_timeout,
        banner_timeout=settings.ssh_connect_timeout,
        auth_timeout=settings.ssh_connect_timeout,
        allow_agent=False,
        look_for_keys=False,
    )

    def connect_with_key() -> None:
        key_path = resolve_private_key_path(credential_ref)
        client.connect(**base, key_filename=key_path)

    def connect_with_password() -> None:
        if not ssh_password:
            raise CredentialError("SSH password not configured for this server.")
        client.connect(**base, password=ssh_password)

    try:
        if mode == "password":
            connect_with_password()
        elif mode == "key":
            connect_with_key()
        else:
            try:
                connect_with_key()
            except paramiko.AuthenticationException:
                connect_with_password()
    except paramiko.AuthenticationException as exc:
        raise CredentialError("Authentication failed (user, key, or password not accepted).") from exc
    except (paramiko.SSHException, socket.timeout, OSError) as exc:
        raise CredentialError(f"Connection failed: {exc}") from exc
