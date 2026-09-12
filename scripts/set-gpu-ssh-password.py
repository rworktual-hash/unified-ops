#!/usr/bin/env python3
"""Set SSH password for AI GPU hosts (165/166). Password via env SSH_GPU_PASSWORD — never commit secrets."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal
from app.models.server import Server

GPU_IPS = ("173.234.75.165", "173.234.75.166")


def main() -> None:
    password = os.environ.get("SSH_GPU_PASSWORD")
    if not password:
        print("Set SSH_GPU_PASSWORD in the environment (do not pass on command line in shell history).")
        sys.exit(1)
    db = SessionLocal()
    try:
        updated = 0
        for ip in GPU_IPS:
            row = db.query(Server).filter(Server.ip_address == ip).first()
            if not row:
                print(f"Skip missing IP {ip}")
                continue
            row.ssh_password = password
            row.ssh_auth_mode = "auto"
            row.ssh_username = "krishna"
            row.is_active = True
            updated += 1
        db.commit()
        print(f"Updated {updated} GPU server(s) with password auth (auto: key then password).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
