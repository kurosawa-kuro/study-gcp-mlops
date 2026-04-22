from __future__ import annotations

from typing import Any, Protocol

from common.ports.inbound.search_usecase import SearchQuery


class RerankingPort(Protocol):
    def rerank(
        self,
        query: SearchQuery,
        candidates: list[dict[str, Any]],
        query_vector: list[float] | None,
    ) -> list[dict[str, Any]]:
        ...
