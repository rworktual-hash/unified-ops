from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import paramiko

from app.monitoring.ssh_connect import connect_ssh_client
from app.services.credentials import CredentialError


@contextmanager
def ssh_session(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> Generator[paramiko.SSHClient, None, None]:
    client = paramiko.SSHClient()
    try:
        connect_ssh_client(
            client,
            host=host,
            port=port,
            username=username,
            credential_ref=credential_ref,
            ssh_password=ssh_password,
            ssh_auth_mode=ssh_auth_mode,
        )
        yield client
    except CredentialError:
        raise
    finally:
        client.close()
