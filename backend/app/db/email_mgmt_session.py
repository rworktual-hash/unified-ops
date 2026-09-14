from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import settings


@lru_cache
def get_email_mgmt_engine() -> Engine | None:
    url = settings.email_mgmt_database_url
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)
