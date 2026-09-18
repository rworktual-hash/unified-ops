#!/usr/bin/env python3
"""List databases/tables on legacy portal MySQL (server-management). Run on nlp-sm with LEGACY_METRICS_DATABASE_URL set."""
from __future__ import annotations

import json
import os
import sys

_backend = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_backend))

from app.config import settings
from app.services.legacy_metrics_sync import discover_legacy_schema, legacy_sync_status, test_legacy_connection
from app.db.session import SessionLocal


def main() -> None:
    if not settings.legacy_metrics_database_url:
        print("Set LEGACY_METRICS_DATABASE_URL in .env (read-only user recommended).")
        print("Example: mysql+pymysql://readonly:SECRET@10.180.1.222:3306/information_schema")
        print("Discover MySQL port first: python scripts/discover-legacy-mysql-via-ssh.py")
        sys.exit(1)

    probe = test_legacy_connection()
    print("Connection:", "OK" if probe.get("ok") else f"FAILED — {probe.get('error') or probe.get('reason')}")
    if not probe.get("ok"):
        sys.exit(1)

    discovery = discover_legacy_schema()
    if not discovery.get("ok"):
        print("Discovery failed:", discovery.get("error"))
        sys.exit(1)

    for db in discovery.get("databases", []):
        print(f"\n=== Database: {db['name']} ===")
        for table in db.get("tables", []):
            print(f"  {table['name']} ({table['row_count']} rows)")
            print(f"    columns: {', '.join(table['columns'][:12])}")
            if len(table["columns"]) > 12:
                print(f"    ... +{len(table['columns']) - 12} more")

    db = SessionLocal()
    try:
        status = legacy_sync_status(db)
    finally:
        db.close()

    print("\n=== Configured streams (edit .env LEGACY_* after review) ===")
    for stream in status.get("streams", []):
        print(
            f"  {stream['domain']}: enabled={stream['enabled']} "
            f"db={stream['database'] or '(set LEGACY_*_DATABASE)'} table={stream['table']} "
            f"local_rows={stream['row_count']}"
        )

    out_path = os.path.join(os.path.dirname(__file__), "..", "legacy-metrics-discovery.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(discovery, fh, indent=2, default=str)
    print(f"\nFull discovery written to {out_path}")


if __name__ == "__main__":
    main()
