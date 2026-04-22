from __future__ import annotations

from typing import Any, Protocol

from common.ports.inbound.search_usecase import SearchQuery


class PropertySearchPort(Protocol):
    def search_candidates(self, query: SearchQuery) -> list[dict[str, Any]]:
        ...
