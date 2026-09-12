from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Generator

import paramiko

from app.config import settings
from app.services.credentials import CredentialError, resolve_private_key_path


@contextmanager
def ssh_session(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
) -> Generator[paramiko.SSHClient, None, None]:
    key_path = resolve_private_key_path(credential_ref)
    client = paramiko.SSHClient()
    if settings.ssh_strict_host_keys:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            key_filename=key_path,
            timeout=settings.ssh_connect_timeout,
            banner_timeout=settings.ssh_connect_timeout,
            auth_timeout=settings.ssh_connect_timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        yield client
    except paramiko.AuthenticationException as exc:
        raise CredentialError("Authentication failed (user or key not accepted).") from exc
    except (paramiko.SSHException, socket.timeout, OSError) as exc:
        raise CredentialError(f"Connection failed: {exc}") from exc
    finally:
        client.close()
