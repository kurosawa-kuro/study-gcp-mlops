"""Domain-side search request / response models.

Mirrors ``app/schemas/search.py`` (Pydantic / HTTP layer) but lives in the
domain so the service layer can be tested without FastAPI. ``SearchFilters``
is a ``TypedDict(total=False)`` to give Ports type-safe access without
forcing every caller to construct a full pydantic model.

The mapper layer (`app/api/mappers/search_mapper.py`) bridges
``app/schemas/`` ↔ ``app/domain/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from app.domain.candidate import RankedCandidate


class SearchFilters(TypedDict, total=False):
    """Type-safe replacement for ``dict[str, Any]`` filter dicts.

    All keys optional. Adapters / Ports should look up keys defensively
    via ``.get()`` so older callers passing partial filters keep working.
    Adding a new filter:
    1. Add the key here
    2. Update ``app/schemas/search.SearchFilters``
    3. Update the BigQuery / Meilisearch adapter SQL/parameter handling
    """

    max_rent: int
    layout: str
    max_walk_min: int
    pet_ok: bool
    max_age: int


@dataclass(frozen=True)
class SearchInput:
    """Service-level search request. Built from HTTP request by mapper layer."""

    query: str
    filters: SearchFilters
    top_k: int
    explain: bool = False


@dataclass(frozen=True)
class SearchResultItem:
    """Domain-side search result row.

    Independent of HTTP serialization. The mapper layer converts to / from
    the Pydantic ``app/schemas/search.SearchResultItem`` for the HTTP
    response. Keeping a parallel domain type lets services be tested
    without pydantic.
    """

    property_id: str
    final_rank: int
    lexical_rank: int
    semantic_rank: int
    me5_score: float
    score: float | None = None
    attributions: dict[str, float] | None = None
    # Phase 6 T1 — BQML auxiliary popularity score.
    popularity_score: float | None = None


@dataclass(frozen=True)
class SearchOutput:
    """Service-level search response."""

    request_id: str
    items: list[SearchResultItem]
    model_path: str | None
    # ``ranked`` carries the underlying ``RankedCandidate`` list.
    ranked: list[RankedCandidate]
