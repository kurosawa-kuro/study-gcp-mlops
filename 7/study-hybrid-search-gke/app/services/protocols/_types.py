"""Named result types for Port return values.

Phase B-4 replaces anonymous ``tuple[str, int]`` / ``tuple[str, int, float]``
shapes in Port signatures with NamedTuples so callers and reviewers can
read field names directly. NamedTuple subclasses ``tuple`` at runtime so
adapters returning bare tuples remain compatible — the change is purely
about static-typing and reading clarity.

These types are exported from ``app.services.protocols.__init__`` for
ergonomic imports.
"""

from __future__ import annotations

from typing import NamedTuple


class LexicalResult(NamedTuple):
    """One lexical hit (Meilisearch / Agent Builder)."""

    property_id: str
    rank: int  # 1-based


class SemanticResult(NamedTuple):
    """One semantic neighbour (BigQuery VECTOR_SEARCH / Vertex Vector Search)."""

    property_id: str
    rank: int  # 1-based
    similarity: float  # [0, 1], higher = more similar (1 - cosine_distance)
