"""Port for semantic candidate-search backends.

Phase 6 T3 — extracted from the monolithic ``BigQueryCandidateRetriever``
so Vertex AI Vector Search (Matching Engine) can be swapped in behind the
same interface. ``BigQueryCandidateRetriever`` composes one
``SemanticSearchPort`` implementation at runtime; the default Phase 5
choice (``BigQuerySemanticSearch``) keeps the existing ``/search``
behaviour unchanged.

Phase B-4 narrowed the return type from ``list[tuple[str, int, float]]``
to ``list[SemanticResult]`` (NamedTuple).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.search import SearchFilters
from app.services.protocols._types import SemanticResult


class SemanticSearchPort(Protocol):
    """Return semantic neighbours of ``query_vector`` as named-tuple records.

    ``rank`` is 1-based and matches the ``semantic_rank`` column on
    ``Candidate`` / ``ranking_log``. ``similarity`` is in ``[0, 1]`` with
    higher = more similar (Phase 5 stores ``1 - cosine_distance`` here).
    """

    def search(
        self,
        *,
        query_vector: list[float],
        filters: SearchFilters,
        top_k: int,
    ) -> list[SemanticResult]: ...
