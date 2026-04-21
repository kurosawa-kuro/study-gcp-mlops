from __future__ import annotations

from typing import Any, Protocol


class CachePort(Protocol):
    def get(self, key: str) -> dict[str, Any] | None:
        ...

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        ...
