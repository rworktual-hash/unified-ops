from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.app_user import AppUser


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(*, user_id: int, email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "email": email, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def authenticate_user(db: Session, email: str, password: str) -> AppUser | None:
    row = db.query(AppUser).filter(AppUser.email == normalize_email(email)).first()
    if not row or not row.is_active:
        return None
    if not verify_password(password, row.password_hash):
        return None
    return row


def ensure_bootstrap_admin(db: Session) -> None:
    if db.query(AppUser).count() > 0:
        return
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    if not email or not password:
        return
    db.add(
        AppUser(
            email=normalize_email(email),
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
    )
    db.commit()
