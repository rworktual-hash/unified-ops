#!/usr/bin/env python3
"""Apply known SSH access: linuxteam + key on DR 148/149 only (165/166 wait for server team)."""
from __future__ import annotations

import os
import sys

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))

from app.db.session import SessionLocal  # noqa: E402
from app.models.server import Server  # noqa: E402

KEY_READY_IPS = frozenset({"81.17.61.148", "81.17.61.149"})
SSH_USERNAME = os.environ.get("SEED_SSH_USERNAME", "linuxteam")
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
            s.ssh_username = SSH_USERNAME
            s.credential_ref = CREDENTIAL_REF
            s.is_active = s.ip_address in KEY_READY_IPS
        db.commit()
        ready = [s.server_name for s in rows if s.is_active]
        pending = [s.server_name for s in rows if not s.is_active]
        print(f"Updated {len(rows)} AI/GPU server(s).")
        print(f"  Active (SSH key ready): {', '.join(ready) or 'none'}")
        print(f"  Inactive (key pending): {', '.join(pending) or 'none'}")
        print(f"  ssh_username={SSH_USERNAME!r}, credential_ref={CREDENTIAL_REF!r}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
