#!/usr/bin/env python3
"""SSH-collect CPU/RAM/disk (and GPU/email queue) for all active servers. Email-mgmt DB sync is separate."""
from __future__ import annotations

import os
import sys

_backend = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_backend))

from app.db.session import SessionLocal  # noqa: E402
from app.services.metrics_collect import collect_all_active_servers  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        ok, failed = collect_all_active_servers(db)
        print(f"Collected: {ok} servers, failed: {failed}")
    finally:
        db.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
