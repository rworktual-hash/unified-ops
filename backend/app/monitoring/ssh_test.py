import socket
import time
from dataclasses import dataclass

import paramiko

from app.config import settings
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
) -> SshTestResult:
    try:
        key_path = resolve_private_key_path(credential_ref)
    except CredentialError as exc:
        return SshTestResult(success=False, message=str(exc))

    client = paramiko.SSHClient()
    if settings.ssh_strict_host_keys:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    start = time.monotonic()
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
    except paramiko.AuthenticationException:
        return SshTestResult(success=False, message="Authentication failed (user or key not accepted on server).")
    except (paramiko.SSHException, socket.timeout, OSError) as exc:
        return SshTestResult(success=False, message=f"Connection failed: {exc}")
    finally:
        client.close()
