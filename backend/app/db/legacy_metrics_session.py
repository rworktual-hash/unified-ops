from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse, urlunparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import settings


def _with_database(base_url: str, database: str | None) -> str:
    parsed = urlparse(base_url)
    path = f"/{database}" if database else ""
    return urlunparse(parsed._replace(path=path))


@lru_cache
def get_legacy_metrics_engine(database: str | None = None) -> Engine | None:
    url = settings.legacy_metrics_database_url
    if not url:
        return None
    return create_engine(
        _with_database(url, database),
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"connect_timeout": 8},
    )
