"""Pydantic schemas for Phase 6 T6 ``/rag`` endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.search import SearchFilters, SearchResultItem


class RagRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    top_k: int = Field(default=20, ge=1, le=100)
    summary_top_n: int = Field(
        default=5,
        ge=1,
        le=20,
        description=(
            "How many top-ranked candidates to hand to the generator. "
            "Kept ≤ 20 to keep prompts short and within token budget."
        ),
    )
    max_output_tokens: int = Field(default=512, ge=64, le=2048)


class RagResponse(BaseModel):
    request_id: str
    results: list[SearchResultItem]
    summary: str
    model_path: str | None = None
    prompt_chars: int
