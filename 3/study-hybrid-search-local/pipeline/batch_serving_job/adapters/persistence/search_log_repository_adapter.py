from __future__ import annotations

from common.ports.inbound.search_usecase import SearchQuery
from pipeline.batch_serving_job.repositories.search_log_repository import log_search_and_increment_impressions


class SearchLogRepositoryAdapter:
    def create_search_log(
        self,
        query: SearchQuery,
        result_ids: list[int],
        me5_scores: dict[int, float] | None = None,
    ) -> int:
        scores_list: list[float] | None = None
        if me5_scores is not None:
            scores_list = [me5_scores.get(rid, 0.0) for rid in result_ids]
        return log_search_and_increment_impressions(
            query=query.q,
            user_id=query.user_id,
            result_ids=result_ids,
            me5_scores=scores_list,
        )
