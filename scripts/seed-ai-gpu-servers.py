#!/usr/bin/env python3
"""Seed the four AI/GPU servers into MariaDB (idempotent by IP)."""
from __future__ import annotations

import argparse
import os
import sys

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models import server as _server_model  # noqa: F401, E402
from app.seed.ai_gpu_servers import seed_ai_gpu_servers  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed AI/GPU servers from project docs")
    parser.add_argument(
        "--ssh-username",
        default=os.environ.get("SEED_SSH_USERNAME", "linuxteam"),
        help="SSH user until server team confirms (env: SEED_SSH_USERNAME)",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        created, skipped = seed_ai_gpu_servers(db, ssh_username=args.ssh_username)
    finally:
        db.close()

    print(f"AI/GPU seed done: {created} created, {skipped} skipped (already in DB).")


if __name__ == "__main__":
    main()
