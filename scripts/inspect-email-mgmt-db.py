#!/usr/bin/env python3
"""List tables/columns in email-management MariaDB (read-only). Run on nlp-sm with EMAIL_MGMT_DATABASE_URL set."""
from __future__ import annotations

import os
import sys

_backend = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_backend))

from sqlalchemy import inspect, text

from app.config import settings
from app.db.email_mgmt_session import get_email_mgmt_engine


def main() -> None:
    if not settings.email_mgmt_database_url:
        print("Set EMAIL_MGMT_DATABASE_URL in .env (read-only user recommended).")
        sys.exit(1)
    engine = get_email_mgmt_engine()
    assert engine is not None
    insp = inspect(engine)
    tables = insp.get_table_names()
    print(f"Database tables ({len(tables)}):")
    for name in sorted(tables):
        cols = [c["name"] for c in insp.get_columns(name)]
        print(f"  {name}: {', '.join(cols)}")
    hint = settings.email_mgmt_events_table
    if hint in tables:
        with engine.connect() as conn:
            row = conn.execute(text(f"SELECT COUNT(*) AS n FROM `{hint}`")).mappings().one()
            print(f"\nRow count in configured events table `{hint}`: {row['n']}")
    else:
        print(f"\nConfigured EMAIL_MGMT_EVENTS_TABLE={hint} not found — adjust .env column names after review.")


if __name__ == "__main__":
    main()
