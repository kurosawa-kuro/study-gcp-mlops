from __future__ import annotations

from pipelines.repositories.ranking_compare_repository import log_ranking_comparison


class RankingCompareRepositoryAdapter:
    def create_compare_log(
        self,
        search_log_id: int,
        meili_result_ids: list[int],
        reranked_result_ids: list[int],
    ) -> int:
        return log_ranking_comparison(
            search_log_id=search_log_id,
            meili_result_ids=meili_result_ids,
            reranked_result_ids=reranked_result_ids,
        )
