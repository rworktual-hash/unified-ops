#!/usr/bin/env python3
"""Remove a server row by IP (does not re-run on seed). Usage: python scripts/remove-server-by-ip.py 82.113.92.40"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal
from app.models.server import Server


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: remove-server-by-ip.py <ip_address>")
        sys.exit(1)
    ip = sys.argv[1].strip()
    db = SessionLocal()
    try:
        row = db.query(Server).filter(Server.ip_address == ip).first()
        if not row:
            print(f"No server with IP {ip}")
            return
        name = row.server_name
        db.delete(row)
        db.commit()
        print(f"Removed {name} ({ip}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
