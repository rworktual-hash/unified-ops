#!/usr/bin/env python3
"""
Find MySQL/MariaDB on AI Insights / server-management (10.180.1.222:4204 SSH).
Run on nlp-sm — read-only checks only (ss, SHOW DATABASES).

Env (or pass via shell):
  SERVER_MGMT_SSH_HOST=10.180.1.222
  SERVER_MGMT_SSH_PORT=4204
  SERVER_MGMT_SSH_USER=root
  SERVER_MGMT_SSH_PASSWORD=...   # never commit

Alternatively set ssh_password on inventory row server-management and use --from-inventory.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

_backend = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_backend))

import paramiko

from app.config import settings
from app.monitoring.ssh_connect import connect_ssh_client
from app.monitoring.ssh_policy import configure_paramiko_client

DEFAULT_HOST = "10.180.1.222"
DEFAULT_PORT = 4204
DEFAULT_USER = "root"

REMOTE_PROBE = r"""
echo '=== SSH host ==='
hostname -f 2>/dev/null || hostname
echo '=== MySQL/MariaDB listeners ==='
(ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null) | grep -E '3306|3307|3308|mysql|maria' || echo '(no obvious mysql listener in ss/netstat)'
echo '=== mysql client ==='
command -v mysql 2>/dev/null || command -v mariadb 2>/dev/null || echo '(mysql/mariadb CLI not in PATH)'
echo '=== SHOW DATABASES (local socket) ==='
mysql -NBe 'SHOW DATABASES' 2>/dev/null | grep -Ev '^(information_schema|performance_schema|mysql|sys)$' || echo '(mysql SHOW DATABASES failed — need credentials or socket auth)'
echo '=== Docker MariaDB/MySQL ==='
docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -Ei 'maria|mysql' || echo '(no docker mysql/mariadb or docker unavailable)'
"""


def _run_ssh(host: str, port: int, user: str, password: str | None, credential_ref: str | None) -> str:
    client = paramiko.SSHClient()
    configure_paramiko_client(client)
    connect_ssh_client(
        client,
        host=host,
        port=port,
        username=user,
        credential_ref=credential_ref,
        ssh_password=password,
        ssh_auth_mode="password" if password else "auto",
    )
    try:
        _, stdout, stderr = client.exec_command(REMOTE_PROBE, timeout=settings.ssh_command_timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            out += f"\n--- stderr ---\n{err}"
        return out
    finally:
        client.close()


def _from_inventory() -> tuple[str, int, str, str | None, str | None]:
    from app.db.session import SessionLocal
    from app.models.server import Server

    db = SessionLocal()
    try:
        row = db.query(Server).filter(Server.server_name == "server-management").first()
        if row is None:
            raise SystemExit("No server-management row in DB — seed inventory or set SERVER_MGMT_SSH_* env vars.")
        return (
            row.ip_address,
            row.ssh_port,
            row.ssh_username,
            row.ssh_password,
            row.credential_ref,
        )
    finally:
        db.close()


def _parse_ports(output: str) -> list[int]:
    ports: set[int] = set()
    for match in re.finditer(r":(\d{4,5})\b", output):
        port = int(match.group(1))
        if port in {3306, 3307, 3308, 33060}:
            ports.add(port)
    return sorted(ports)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover MySQL on server-management via SSH (4204).")
    parser.add_argument("--from-inventory", action="store_true", help="Use server-management row from MariaDB")
    args = parser.parse_args()

    if args.from_inventory:
        host, port, user, password, cred = _from_inventory()
    else:
        host = os.environ.get("SERVER_MGMT_SSH_HOST", DEFAULT_HOST)
        port = int(os.environ.get("SERVER_MGMT_SSH_PORT", str(DEFAULT_PORT)))
        user = os.environ.get("SERVER_MGMT_SSH_USER", DEFAULT_USER)
        password = os.environ.get("SERVER_MGMT_SSH_PASSWORD")
        cred = None if password else "gpu_key_1"

    if not password and not cred and not args.from_inventory:
        print(
            "Set SERVER_MGMT_SSH_PASSWORD (or --from-inventory with ssh_password on server-management).\n"
            f"Example: SERVER_MGMT_SSH_PASSWORD='...' python {sys.argv[0]}"
        )
        sys.exit(1)

    print(f"SSH probe: {user}@{host}:{port}\n")
    try:
        output = _run_ssh(host, port, user, password, cred)
    except Exception as exc:
        print(f"SSH failed: {exc}")
        sys.exit(1)

    print(output)

    ports = _parse_ports(output)
    mysql_port = ports[0] if ports else 3306
    connect_host = host
    if host == "82.113.72.52":
        print("\nTip: from nlp-sm internal network you may prefer SERVER_MGMT_SSH_HOST=10.180.1.222")

    print("\n=== Suggested .env (adjust user/password after creating read-only DB user) ===")
    print(
        f"LEGACY_METRICS_DATABASE_URL=mysql+pymysql://readonly:URL_ENCODED_PASSWORD@"
        f"{connect_host}:{mysql_port}/information_schema"
    )
    print("\nThen: python scripts/inspect-legacy-metrics-db.py")


if __name__ == "__main__":
    main()
