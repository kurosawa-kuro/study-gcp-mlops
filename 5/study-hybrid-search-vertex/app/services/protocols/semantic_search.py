"""Port for semantic candidate-search backends."""

from __future__ import annotations

from typing import Any, Protocol


class SemanticSearchPort(Protocol):
    """Return semantic neighbours as ``(property_id, rank, similarity)``."""

    def search(
        self,
        *,
        query_vector: list[float],
        filters: dict[str, Any],
        top_k: int,
    ) -> list[tuple[str, int, float]]: ...
