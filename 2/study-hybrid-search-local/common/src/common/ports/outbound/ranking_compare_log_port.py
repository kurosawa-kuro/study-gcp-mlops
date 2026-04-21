from __future__ import annotations

from typing import Protocol


class RankingCompareLogPort(Protocol):
    def create_compare_log(
        self,
        search_log_id: int,
        meili_result_ids: list[int],
        reranked_result_ids: list[int],
    ) -> int:
        ...
