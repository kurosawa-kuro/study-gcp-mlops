"""Unit tests for ``RagService`` (Phase 6 T6)."""

from __future__ import annotations

from app.domain.candidate import Candidate
from app.domain.search import SearchInput
from app.services.rag_service import RagService
from app.services.rag_summarizer import RagSummarizer
from app.services.search_service import SearchService
from tests.fakes import (
    InMemoryCandidateRetriever,
    InMemoryRankingLogPublisher,
    StubEncoderClient,
    StubGenerator,
)


def _make_candidate(property_id: str) -> Candidate:
    return Candidate(
        property_id=property_id,
        lexical_rank=1,
        semantic_rank=1,
        me5_score=0.5,
        property_features={
            "rent": 100000,
            "walk_min": 5,
            "age_years": 8,
            "area_m2": 30.0,
            "ctr": 0.1,
        },
    )


def test_summarize_calls_generator_with_top_n_context() -> None:
    candidates = [_make_candidate(f"P-{i:03d}") for i in range(1, 6)]
    retriever = InMemoryCandidateRetriever(candidates=candidates)
    search_service = SearchService(
        retriever_default=retriever,
        retriever_alt=None,
        encoder=StubEncoderClient(),
        publisher=InMemoryRankingLogPublisher(),
    )
    generator = StubGenerator(response="渋谷 1LDK のおすすめ 3 件")
    summarizer = RagSummarizer(generator=generator)
    service = RagService(search_service=search_service, summarizer=summarizer)

    output = service.summarize(
        request_id="rag-1",
        input=SearchInput(query="渋谷 1LDK", filters={}, top_k=10),
        summary_top_n=3,
    )

    assert output.summary == "渋谷 1LDK のおすすめ 3 件"
    assert output.prompt_chars > 0
    assert len(generator.calls) == 1
    # Prompt should reference the user query so RAG hallucination is bounded.
    assert "渋谷 1LDK" in generator.calls[0].prompt
