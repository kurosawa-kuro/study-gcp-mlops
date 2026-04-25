"""Process-local TTL cache implementation of ``CacheStore``.

Default Phase 7 cache; replaced by ``MemorystoreRedisCacheStore`` once
Redis is wired in (currently a stub in ``adapters/cache_store.py``).
"""

from __future__ import annotations

from threading import RLock
from typing import Any

from cachetools import TTLCache

from app.services.protocols.cache_store import CacheStore


class InMemoryTTLCacheStore(CacheStore):
    """Thread-safe process-local cache with TTL semantics.

    ``cachetools.TTLCache`` applies TTL at cache construction time, so this
    adapter uses ``default_ttl_seconds`` as the source of truth and accepts
    the per-call ``ttl_seconds`` parameter for interface compatibility
    (the value is ignored — all entries expire after ``default_ttl_seconds``).
    """

    def __init__(self, *, maxsize: int = 2048, default_ttl_seconds: int = 120) -> None:
        self._ttl_seconds = max(1, int(default_ttl_seconds))
        self._cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=maxsize,
            ttl=self._ttl_seconds,
        )
        self._lock = RLock()

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            with self._lock:
                value = self._cache.get(key)
                if value is None:
                    return None
                return dict(value)
        except Exception:
            return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        _ = ttl_seconds
        try:
            with self._lock:
                self._cache[key] = dict(value)
        except Exception:
            return None
