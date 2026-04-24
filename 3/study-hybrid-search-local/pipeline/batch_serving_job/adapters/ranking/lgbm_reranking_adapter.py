from __future__ import annotations

from typing import Any

from common.ports.inbound.search_usecase import SearchQuery
from pipeline.batch_serving_job.repositories.property_embedding_repository import fetch_property_embeddings
from pipeline.batch_serving_job.services.embeddings.similarity_service import cosine_similarity
from pipeline.batch_serving_job.services.ranking.lgbm_reranker import rerank_with_lgbm


class LightGBMRerankingAdapter:
    def rerank(
        self,
        query: SearchQuery,
        candidates: list[dict[str, Any]],
        query_vector: list[float] | None,
    ) -> list[dict[str, Any]]:
        items = [dict(c) for c in candidates]

        if query_vector:
            property_ids = [int(item["id"]) for item in items if item.get("id") is not None]
            embedding_map = fetch_property_embeddings(property_ids)
            for item in items:
                pid = item.get("id")
                score = 0.0
                if pid is not None:
                    doc_vector = embedding_map.get(int(pid))
                    if doc_vector:
                        score = cosine_similarity(query_vector, doc_vector)
                item["me5_score"] = float(round(score, 6))
        else:
            for item in items:
                item.setdefault("me5_score", 0.0)

        return rerank_with_lgbm(items)
