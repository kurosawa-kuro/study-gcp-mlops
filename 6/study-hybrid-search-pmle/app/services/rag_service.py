"""``RagService`` — /rag orchestration (Phase 6 T6).

Reuses :class:`SearchService` for the retrieval + rerank step, then asks
the injected :class:`RagSummarizer` (Generator-backed) to summarize the
top-N candidates. Keeps the original /search contract intact — this is
strictly additive.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.search import SearchInput, SearchOutput
from app.services.rag_summarizer import RagSummarizer
from app.services.search_service import SearchService, SearchServiceUnavailable


@dataclass(frozen=True)
class RagOutput:
    """Service-level /rag response."""

    request_id: str
    output: SearchOutput
    summary: str
    prompt_chars: int


class RagService:
    """Hybrid search + LLM summary use case."""

    def __init__(
        self,
        *,
        search_service: SearchService,
        summarizer: RagSummarizer,
    ) -> None:
        self._search_service = search_service
        self._summarizer = summarizer

    def summarize(
        self,
        *,
        request_id: str,
        input: SearchInput,
        summary_top_n: int | None = None,
    ) -> RagOutput:
        # /rag uses the same retrieval pipeline as /search; explain is
        # irrelevant for summarization. Rebuild the input to enforce these.
        search_input = SearchInput(
            query=input.query,
            filters=input.filters,
            top_k=input.top_k,
            explain=False,
        )
        try:
            output = self._search_service.search(request_id=request_id, input=search_input)
        except SearchServiceUnavailable:
            raise
        summary = self._summarizer.summarize(
            query=input.query,
            ranked=output.ranked,
            top_n=summary_top_n,
        )
        return RagOutput(
            request_id=request_id,
            output=output,
            summary=summary.summary,
            prompt_chars=summary.prompt_chars,
        )
