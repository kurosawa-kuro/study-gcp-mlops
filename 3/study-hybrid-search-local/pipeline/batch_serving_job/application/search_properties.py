from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.ports.inbound.search_usecase import SearchQuery
from common.ports.outbound.cache_port import CachePort
from common.ports.outbound.embedding_port import EmbeddingPort
from common.ports.outbound.property_search_port import PropertySearchPort
from common.ports.outbound.ranking_compare_log_port import RankingCompareLogPort
from common.ports.outbound.reranking_port import RerankingPort
from common.ports.outbound.search_log_port import SearchLogPort


@dataclass
class SearchPropertiesUseCase:
    property_search_port: PropertySearchPort
    embedding_port: EmbeddingPort
    reranking_port: RerankingPort
    cache_port: CachePort
    search_log_port: SearchLogPort
    ranking_compare_log_port: RankingCompareLogPort
    cache_ttl_seconds: int = 120

    def execute(self, query: SearchQuery) -> dict[str, Any]:
        cache_key = self._build_cache_key(query)
        cached = self.cache_port.get(cache_key)
        if cached is not None:
            return cached

        candidates = self.property_search_port.search_candidates(query)
        query_vector = self.embedding_port.embed_query(query.q) if query.q else None
        reranked = self.reranking_port.rerank(query, candidates, query_vector)

        meili_ids = [int(c["id"]) for c in candidates if c.get("id") is not None]
        result_ids = [int(item["id"]) for item in reranked if item.get("id") is not None]
        me5_scores = {
            int(item["id"]): float(item.get("me5_score", 0.0))
            for item in reranked
            if item.get("id") is not None
        }

        search_log_id = self.search_log_port.create_search_log(
            query=query,
            result_ids=result_ids,
            me5_scores=me5_scores,
        )
        compare_log_id = self.ranking_compare_log_port.create_compare_log(
            search_log_id=search_log_id,
            meili_result_ids=meili_ids,
            reranked_result_ids=result_ids,
        )

        response: dict[str, Any] = {
            "search_log_id": search_log_id,
            "compare_log_id": compare_log_id,
            "count": len(reranked),
            "items": reranked[: query.limit],
        }
        self.cache_port.set(cache_key, response, self.cache_ttl_seconds)
        return response

    def _build_cache_key(self, query: SearchQuery) -> str:
        return (
            f"search:q={query.q}|city={query.city}|layout={query.layout}|"
            f"price_lte={query.price_lte}|pet={query.pet}|walk_min={query.walk_min}|"
            f"limit={query.limit}|candidate_limit={query.candidate_limit}"
        )
