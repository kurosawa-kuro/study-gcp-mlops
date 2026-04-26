"""Production ``CacheStore`` adapters."""

from __future__ import annotations

from typing import Any

from app.services.protocols.cache_store import CacheStore


class MemorystoreRedisCacheStore(CacheStore):
    """Reserved for future Memorystore rollout.

    Phase R4 does not use Redis in this repository. Keep this class as a
    compatibility shim so the composition root can switch implementation
    later without changing service code.
    """

    def get(self, key: str) -> dict[str, Any] | None:
        return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        return None


__all__ = ["MemorystoreRedisCacheStore"]
