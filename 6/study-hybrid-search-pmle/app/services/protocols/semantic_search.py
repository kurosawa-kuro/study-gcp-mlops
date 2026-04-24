"""Port for semantic candidate-search backends.

Phase 6 T3 — extracted from the monolithic ``BigQueryCandidateRetriever``
so Vertex AI Vector Search (Matching Engine) can be swapped in behind the
same interface. ``BigQueryCandidateRetriever`` now composes one
``SemanticSearchPort`` implementation at runtime; the default Phase 5
choice (``BigQuerySemanticSearch``) keeps the existing ``/search``
behaviour unchanged.
"""

from __future__ import annotations

from typing import Any, Protocol


class SemanticSearchPort(Protocol):
    """Return semantic neighbours of ``query_vector`` as ``(property_id, rank, similarity)``.

    ``rank`` is 1-based and matches the ``semantic_rank`` column on
    ``Candidate`` / ``ranking_log``. ``similarity`` is in ``[0, 1]`` with
    higher = more similar (Phase 5 stores ``1 - cosine_distance`` here).
    ``filters`` mirrors the shape of :class:`app.schemas.search.SearchFilters`.
    """

    def search(
        self,
        *,
        query_vector: list[float],
        filters: dict[str, Any],
        top_k: int,
    ) -> list[tuple[str, int, float]]: ...
