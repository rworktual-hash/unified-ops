"""Short in-process cache so 5s UI polls do not stampede MariaDB .222."""

from __future__ import annotations

import time
from typing import Any

TTL_SECONDS = 2.0
_STORE: dict[str, tuple[float, Any]] = {}


def get_cached(key: str, ttl: float = TTL_SECONDS) -> Any | None:
    hit = _STORE.get(key)
    if not hit:
        return None
    stamp, value = hit
    if time.monotonic() - stamp >= ttl:
        return None
    return value


def set_cached(key: str, value: Any) -> None:
    _STORE[key] = (time.monotonic(), value)
