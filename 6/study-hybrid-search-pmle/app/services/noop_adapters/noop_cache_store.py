"""Null ``CacheStore`` implementation — get always returns None, set is a no-op."""

from __future__ import annotations

from typing import Any

from app.services.protocols.cache_store import CacheStore


class NoopCacheStore(CacheStore):
    """Disable caching path. Selected when ``SEARCH_CACHE_TTL_SECONDS <= 0``."""

    def get(self, key: str) -> dict[str, Any] | None:
        return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        return None
