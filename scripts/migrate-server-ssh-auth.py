#!/usr/bin/env python3
"""Add ssh_password and ssh_auth_mode columns to existing MariaDB (safe to re-run)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import inspect, text

from app.db.session import engine


def main() -> None:
    insp = inspect(engine)
    if "servers" not in insp.get_table_names():
        print("No servers table yet — start API once to create schema.")
        return
    cols = {c["name"] for c in insp.get_columns("servers")}
    with engine.begin() as conn:
        if "ssh_password" not in cols:
            conn.execute(text("ALTER TABLE servers ADD COLUMN ssh_password VARCHAR(512) NULL"))
            print("Added ssh_password")
        else:
            print("ssh_password already exists")
        if "ssh_auth_mode" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE servers ADD COLUMN ssh_auth_mode VARCHAR(16) NOT NULL DEFAULT 'auto'"
                )
            )
            print("Added ssh_auth_mode")
        else:
            print("ssh_auth_mode already exists")
    print("Migration done.")


if __name__ == "__main__":
    main()
