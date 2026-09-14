#!/usr/bin/env python3
"""Create or reset the admin login (email + password). Run on nlp-sm only — never commit passwords."""
from __future__ import annotations

import os
import sys

_backend = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_backend))

from app.db.session import SessionLocal  # noqa: E402
from app.models.app_user import AppUser  # noqa: E402
from app.services.app_auth import hash_password, normalize_email  # noqa: E402


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        print("Set ADMIN_EMAIL and ADMIN_PASSWORD in the environment.")
        sys.exit(1)
    email = normalize_email(email)
    db = SessionLocal()
    try:
        row = db.query(AppUser).filter(AppUser.email == email).first()
        if row:
            row.password_hash = hash_password(password)
            row.role = "admin"
            row.is_active = True
            print(f"Updated admin password for {email}")
        else:
            db.add(
                AppUser(
                    email=email,
                    password_hash=hash_password(password),
                    role="admin",
                    is_active=True,
                )
            )
            print(f"Created admin {email}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
