#!/usr/bin/env python3
"""Upsert full server inventory from KT / domain guides."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal
from app.seed.full_inventory import ALL_INVENTORY, upsert_inventory


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or update all inventory servers by IP")
    parser.add_argument(
        "--no-update-existing",
        action="store_true",
        help="Only insert new IPs; do not refresh existing rows",
    )
    args = parser.parse_args()
    db = SessionLocal()
    try:
        created, updated, skipped = upsert_inventory(db, update_existing=not args.no_update_existing)
        print(f"Inventory upsert done: {created} created, {updated} updated, {skipped} skipped.")
        print(f"Total defined in catalog: {len(ALL_INVENTORY)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
