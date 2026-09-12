"""SSH host-key policy for non-interactive monitoring (no yes/no fingerprint prompt)."""

import paramiko

from app.config import settings


def configure_paramiko_client(client: paramiko.SSHClient) -> None:
    if settings.ssh_strict_host_keys:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
