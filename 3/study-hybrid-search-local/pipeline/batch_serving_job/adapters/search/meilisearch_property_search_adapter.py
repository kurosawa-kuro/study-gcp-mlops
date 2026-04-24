from __future__ import annotations

from typing import Any

from common.clients.meilisearch_client import MeiliClient
from common.ports.inbound.search_usecase import SearchQuery
from pipeline.batch_serving_job.services.search.query_filter_builder import build_search_payload


class MeilisearchPropertySearchAdapter:
    def __init__(self, client: MeiliClient) -> None:
        self._client = client

    def search_candidates(self, query: SearchQuery) -> list[dict[str, Any]]:
        payload = build_search_payload(
            q=query.q,
            city=query.city,
            layout=query.layout,
            price_lte=query.price_lte,
            pet=query.pet,
            walk_min=query.walk_min,
            candidate_limit=query.candidate_limit,
        )
        result = self._client.search(payload)
        hits = result.get("hits", [])[: query.candidate_limit]
        return [
            {
                "id": hit.get("id"),
                "title": hit.get("title"),
                "city": hit.get("city"),
                "price": hit.get("price"),
                "layout": hit.get("layout"),
                "walk_min": hit.get("walk_min"),
                "pet": hit.get("pet"),
            }
            for hit in hits
        ]
