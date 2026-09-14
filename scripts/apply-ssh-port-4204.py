#!/usr/bin/env python3
"""Sync ssh_port from full_inventory into MariaDB (22 or 4204 per host)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal
from app.models.server import Server
from app.seed.full_inventory import ALL_INVENTORY


def main() -> None:
    target_by_ip = {row.ip_address: row.ssh_port for row in ALL_INVENTORY}
    db = SessionLocal()
    try:
        updated = 0
        for row in db.query(Server).all():
            expected = target_by_ip.get(row.ip_address)
            if expected is None or row.ssh_port == expected:
                continue
            print(f"  {row.server_name} ({row.ip_address}): {row.ssh_port} -> {expected}")
            row.ssh_port = expected
            updated += 1
        db.commit()
        print(f"Updated ssh_port on {updated} server(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
