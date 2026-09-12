#!/usr/bin/env python3
"""Set credential_ref=gpu_key_1 on all seeded AI/GPU servers (by project=ai, type=gpu)."""
from __future__ import annotations

import os
import sys

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))

from app.db.session import SessionLocal  # noqa: E402
from app.models.server import Server  # noqa: E402


def main() -> None:
    ref = os.environ.get("CREDENTIAL_REF", "gpu_key_1")
    db = SessionLocal()
    try:
        rows = (
            db.query(Server)
            .filter(Server.project == "ai", Server.server_type == "gpu")
            .all()
        )
        for s in rows:
            s.credential_ref = ref
        db.commit()
        print(f"Updated credential_ref={ref!r} on {len(rows)} AI/GPU server(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
