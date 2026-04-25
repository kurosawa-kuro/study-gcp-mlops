"""Null ``LexicalSearchPort`` — returns empty result list.

Selected when ``MEILI_BASE_URL`` is empty AND no Agent Builder backend is
configured. Hybrid retrieval still runs the semantic side; the RRF fusion
falls back to semantic-only ordering.
"""

from __future__ import annotations

from typing import Any

from app.services.protocols.lexical_search import LexicalSearchPort


class NoopLexicalSearch(LexicalSearchPort):
    def search(
        self,
        *,
        query: str,
        filters: dict[str, Any],
        top_k: int,
    ) -> list[tuple[str, int]]:
        return []
