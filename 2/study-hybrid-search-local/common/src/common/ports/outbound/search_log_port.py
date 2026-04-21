from __future__ import annotations

from typing import Protocol

from common.ports.inbound.search_usecase import SearchQuery


class SearchLogPort(Protocol):
    def create_search_log(
        self,
        query: SearchQuery,
        result_ids: list[int],
        me5_scores: dict[int, float] | None = None,
    ) -> int:
        ...
