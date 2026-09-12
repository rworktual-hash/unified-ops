import time
from dataclasses import dataclass

import paramiko

from app.config import settings
from app.monitoring.ssh_connect import connect_ssh_client
from app.services.credentials import CredentialError, resolve_private_key_path


@dataclass
class SshTestResult:
    success: bool
    message: str
    latency_ms: int | None = None


def test_ssh_connection(
    *,
    host: str,
    port: int,
    username: str,
    credential_ref: str | None,
    ssh_password: str | None = None,
    ssh_auth_mode: str = "auto",
) -> SshTestResult:
    try:
        if ssh_auth_mode == "key" or (ssh_auth_mode == "auto" and not ssh_password):
            resolve_private_key_path(credential_ref)
    except CredentialError as exc:
        return SshTestResult(success=False, message=str(exc))

    client = paramiko.SSHClient()
    start = time.monotonic()
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
        _stdin, stdout, _stderr = client.exec_command("echo unified_ops_ok", timeout=settings.ssh_command_timeout)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        exit_status = stdout.channel.recv_exit_status()
        latency_ms = int((time.monotonic() - start) * 1000)
        if exit_status != 0 or "unified_ops_ok" not in output:
            return SshTestResult(
                success=False,
                message=f"Connected but verification command failed (exit {exit_status}).",
                latency_ms=latency_ms,
            )
        return SshTestResult(success=True, message="SSH connection and test command OK.", latency_ms=latency_ms)
    except CredentialError as exc:
        return SshTestResult(success=False, message=str(exc))
    finally:
        client.close()
