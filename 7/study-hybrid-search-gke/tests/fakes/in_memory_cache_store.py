"""In-memory ``CacheStore`` for tests that need round-trip behaviour."""

from __future__ import annotations

from typing import Any

from app.services.protocols.cache_store import CacheStore


class InMemoryCacheStore(CacheStore):
    """Deterministic dict-backed cache; ignores TTL.

    Differs from ``app.services.noop_adapters.in_memory_cache_store.InMemoryTTLCacheStore``
    (production) in that this one is dead simple — no eviction, no
    threading. Test code wants ``set / get`` round-trip and call
    inspection.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self.gets: list[str] = []
        self.sets: list[tuple[str, dict[str, Any], int]] = []

    def get(self, key: str) -> dict[str, Any] | None:
        self.gets.append(key)
        value = self._store.get(key)
        return None if value is None else dict(value)

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self.sets.append((key, dict(value), ttl_seconds))
        self._store[key] = dict(value)
