#!/usr/bin/env python3
"""Apply known SSH access: linuxteam+key on 148/149; krishna+auto on 165/166 (password via DB)."""
from __future__ import annotations

import os
import sys

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))

from app.db.session import SessionLocal  # noqa: E402
from app.models.server import Server  # noqa: E402

KEY_READY_IPS = frozenset({"81.17.61.148", "81.17.61.149"})
KRISHNA_IPS = frozenset({"173.234.75.165", "173.234.75.166"})
CREDENTIAL_REF = os.environ.get("CREDENTIAL_REF", "gpu_key_1")


def main() -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(Server)
            .filter(Server.project == "ai", Server.server_type == "gpu")
            .all()
        )
        for s in rows:
            s.credential_ref = CREDENTIAL_REF
            if s.ip_address in KRISHNA_IPS:
                s.ssh_username = "krishna"
                s.ssh_auth_mode = "auto"
                s.is_active = bool(s.ssh_password)
            elif s.ip_address in KEY_READY_IPS:
                s.ssh_username = os.environ.get("SEED_SSH_USERNAME", "linuxteam")
                s.ssh_auth_mode = "key"
                s.is_active = True
            else:
                s.ssh_username = os.environ.get("SEED_SSH_USERNAME", "linuxteam")
                s.ssh_auth_mode = "key"
                s.is_active = s.ip_address in KEY_READY_IPS
        db.commit()
        ready = [s.server_name for s in rows if s.is_active]
        pending = [s.server_name for s in rows if not s.is_active]
        print(f"Updated {len(rows)} AI/GPU server(s).")
        print(f"  Active: {', '.join(ready) or 'none'}")
        print(f"  Inactive: {', '.join(pending) or 'none'}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
