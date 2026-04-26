"""Port for semantic candidate-search backends.

Phase 6 keeps the semantic search step behind a Protocol so the
``BigQueryCandidateRetriever`` composes a dedicated semantic adapter instead
of inlining query construction.
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
