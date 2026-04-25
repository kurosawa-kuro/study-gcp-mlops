"""Phase 6 T7 — Discovery Engine (Vertex AI Agent Builder) lexical adapter.

Alternative backend for the ``LexicalSearchPort`` used by
``BigQueryCandidateRetriever``. The Phase 5 Meilisearch adapter stays
primary (親リポ non-negotiable: "LightGBM + ME5 + Meilisearch"); this
adapter is a 副-経路 (副経路) exercised only when the caller opts in via
``/search?lexical=agent_builder``.

Returns ``(property_id, rank)`` tuples shaped the same as
``MeilisearchLexical`` so downstream RRF fusion stays untouched.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.protocols._types import LexicalResult

logger = logging.getLogger("app.agent_builder_lexical")


class AgentBuilderLexicalRetriever:
    """Discovery Engine ``SearchService.Search`` over a properties Datastore.

    Args:
        project_id: GCP project.
        location: Discovery Engine collection location (usually ``global``).
        engine_id: Discovery Engine SearchApp / Engine ID created by
            ``infra/terraform/modules/agent_builder``.
        collection_id: Typically ``default_collection``.
        serving_config_id: Typically ``default_search``.
        client: optional injected client (tests).
    """

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        engine_id: str,
        collection_id: str = "default_collection",
        serving_config_id: str = "default_search",
        client: Any | None = None,
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._engine_id = engine_id
        self._collection_id = collection_id
        self._serving_config_id = serving_config_id
        self._client = client
        logger.info(
            "AgentBuilderLexicalRetriever init project=%s location=%s engine=%s",
            project_id,
            location,
            engine_id,
        )

    def _service(self) -> Any:
        if self._client is not None:
            return self._client
        # Lazy import so unit tests can stub the adapter without requiring
        # google-cloud-discoveryengine to be installed. The package is an
        # optional runtime dep (see pyproject.toml). mypy runs in strict
        # mode without the package present, so tolerate the missing
        # submodule via importlib.
        import importlib

        discoveryengine = importlib.import_module("google.cloud.discoveryengine_v1")
        self._client = discoveryengine.SearchServiceClient()
        return self._client

    def _serving_config_path(self) -> str:
        return (
            f"projects/{self._project_id}/locations/{self._location}/"
            f"collections/{self._collection_id}/engines/{self._engine_id}/"
            f"servingConfigs/{self._serving_config_id}"
        )

    def search(
        self,
        *,
        query: str,
        filters: dict[str, Any],
        top_k: int,
    ) -> list[LexicalResult]:
        import importlib

        discoveryengine = importlib.import_module("google.cloud.discoveryengine_v1")
        service = self._service()
        request = discoveryengine.SearchRequest(
            serving_config=self._serving_config_path(),
            query=query,
            page_size=top_k,
            filter=_build_filter(filters),
        )
        try:
            response = service.search(request=request)
        except Exception:
            logger.exception(
                "AgentBuilder search failed engine=%s query_len=%d",
                self._engine_id,
                len(query),
            )
            raise
        out: list[LexicalResult] = []
        # ``results`` is a pager: iterate once to capture ``top_k`` hits.
        for rank, result in enumerate(response.results, start=1):
            if rank > top_k:
                break
            doc_id = getattr(result.document, "id", None) or ""
            if not doc_id:
                continue
            out.append(LexicalResult(property_id=str(doc_id), rank=rank))
        return out


def _build_filter(filters: dict[str, Any]) -> str:
    """Translate SearchFilters into a Discovery Engine filter expression.

    Discovery Engine supports structured filters over indexed fields. Only
    non-None filters are included; the expression is conjunctive.
    """
    clauses: list[str] = []
    max_rent = filters.get("max_rent")
    if isinstance(max_rent, int):
        clauses.append(f"rent <= {max_rent}")
    layout = filters.get("layout")
    if isinstance(layout, str) and layout:
        clauses.append(f'layout: ANY("{layout}")')
    max_walk_min = filters.get("max_walk_min")
    if isinstance(max_walk_min, int):
        clauses.append(f"walk_min <= {max_walk_min}")
    pet_ok = filters.get("pet_ok")
    if isinstance(pet_ok, bool):
        clauses.append(f"pet_ok = {'true' if pet_ok else 'false'}")
    max_age = filters.get("max_age")
    if isinstance(max_age, int):
        clauses.append(f"age_years <= {max_age}")
    return " AND ".join(clauses)
