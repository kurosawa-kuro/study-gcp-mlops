"""Unit tests for ``app.api.mappers.search_mapper``."""

from __future__ import annotations

from app.api.mappers.search_mapper import (
    rag_request_to_search_input,
    search_request_to_input,
    to_rag_response,
    to_search_response,
)
from app.domain.candidate import RankedCandidate
from app.domain.candidate import Candidate
from app.domain.search import SearchOutput, SearchResultItem
from app.schemas.rag import RagRequest
from app.schemas.search import SearchFilters as SchemaFilters, SearchRequest
from app.services.rag_service import RagOutput


def test_search_request_to_input_propagates_filters_and_flags() -> None:
    req = SearchRequest(
        query="渋谷",
        filters=SchemaFilters(max_rent=200000, layout="1LDK", pet_ok=True),
        top_k=10,
    )
    domain = search_request_to_input(req, explain=True, lexical_backend="agent_builder")

    assert domain.query == "渋谷"
    assert domain.top_k == 10
    assert domain.explain is True
    assert domain.lexical_backend == "agent_builder"
    assert domain.filters.get("max_rent") == 200000
    assert domain.filters.get("layout") == "1LDK"
    assert domain.filters.get("pet_ok") is True
    # Unset filters must not appear in the TypedDict (total=False semantics)
    assert "max_walk_min" not in domain.filters
    assert "max_age" not in domain.filters


def test_rag_request_keeps_meili_default_and_no_explain() -> None:
    req = RagRequest(query="x", top_k=20, summary_top_n=3)
    domain = rag_request_to_search_input(req)

    assert domain.lexical_backend == "meili"
    assert domain.explain is False


def test_to_search_response_maps_items() -> None:
    items = [
        SearchResultItem(
            property_id="P-001",
            final_rank=1,
            lexical_rank=1,
            semantic_rank=2,
            me5_score=0.5,
            score=0.99,
            attributions={"rent": 0.1, "_baseline": 0.0},
            popularity_score=0.4,
        ),
    ]
    output = SearchOutput(
        request_id="r-1",
        items=items,
        model_path="gs://models/foo",
        ranked=[],
    )
    response = to_search_response(output)

    assert response.request_id == "r-1"
    assert response.model_path == "gs://models/foo"
    assert len(response.results) == 1
    assert response.results[0].property_id == "P-001"
    assert response.results[0].popularity_score == 0.4


def test_to_rag_response_maps_summary_and_prompt_chars() -> None:
    candidate = Candidate(
        property_id="P-1",
        lexical_rank=1,
        semantic_rank=1,
        me5_score=0.4,
        property_features={},
    )
    inner_output = SearchOutput(
        request_id="r-rag",
        items=[
            SearchResultItem(
                property_id="P-1",
                final_rank=1,
                lexical_rank=1,
                semantic_rank=1,
                me5_score=0.4,
            ),
        ],
        model_path=None,
        ranked=[RankedCandidate(candidate=candidate, final_rank=1, score=None)],
    )
    rag_output = RagOutput(
        request_id="r-rag",
        output=inner_output,
        summary="ok",
        prompt_chars=42,
    )
    response = to_rag_response(rag_output)

    assert response.summary == "ok"
    assert response.prompt_chars == 42
    assert len(response.results) == 1
