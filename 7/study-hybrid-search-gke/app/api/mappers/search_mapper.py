"""Pydantic ↔ domain converters for /search and /rag.

The HTTP layer speaks Pydantic (``app.schemas``), the service layer speaks
domain models (``app.domain``). These functions are the only place the
two vocabularies meet.
"""

from __future__ import annotations

from app.domain.search import (
    SearchFilters,
    SearchInput,
    SearchOutput,
    SearchResultItem,
)
from app.schemas.rag import RagRequest, RagResponse
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem as SchemaSearchResultItem,
)
from app.services.rag_service import RagOutput


def _filters_from_pydantic(raw: dict[str, object]) -> SearchFilters:
    """Coerce a Pydantic ``SearchFilters.model_dump()`` dict to TypedDict.

    Skips ``None`` so ``total=False`` semantics hold (absent key ≠ None).
    """
    out: SearchFilters = {}
    if raw.get("max_rent") is not None:
        out["max_rent"] = int(raw["max_rent"])  # type: ignore[arg-type]
    if raw.get("layout") is not None:
        out["layout"] = str(raw["layout"])
    if raw.get("max_walk_min") is not None:
        out["max_walk_min"] = int(raw["max_walk_min"])  # type: ignore[arg-type]
    if raw.get("pet_ok") is not None:
        out["pet_ok"] = bool(raw["pet_ok"])
    if raw.get("max_age") is not None:
        out["max_age"] = int(raw["max_age"])  # type: ignore[arg-type]
    return out


def search_request_to_input(
    req: SearchRequest,
    *,
    explain: bool = False,
    lexical_backend: str = "meili",
) -> SearchInput:
    return SearchInput(
        query=req.query,
        filters=_filters_from_pydantic(req.filters.model_dump()),
        top_k=req.top_k,
        explain=explain,
        lexical_backend=lexical_backend,
    )


def rag_request_to_search_input(req: RagRequest) -> SearchInput:
    return SearchInput(
        query=req.query,
        filters=_filters_from_pydantic(req.filters.model_dump()),
        top_k=req.top_k,
        explain=False,
        lexical_backend="meili",
    )


def search_result_item_to_schema(item: SearchResultItem) -> SchemaSearchResultItem:
    return SchemaSearchResultItem(
        property_id=item.property_id,
        final_rank=item.final_rank,
        lexical_rank=item.lexical_rank,
        semantic_rank=item.semantic_rank,
        me5_score=item.me5_score,
        score=item.score,
        attributions=item.attributions,
        popularity_score=item.popularity_score,
    )


def to_search_response(output: SearchOutput) -> SearchResponse:
    return SearchResponse(
        request_id=output.request_id,
        results=[search_result_item_to_schema(it) for it in output.items],
        model_path=output.model_path,
    )


def to_rag_response(output: RagOutput) -> RagResponse:
    return RagResponse(
        request_id=output.request_id,
        results=[search_result_item_to_schema(it) for it in output.output.items],
        summary=output.summary,
        model_path=output.output.model_path,
        prompt_chars=output.prompt_chars,
    )
