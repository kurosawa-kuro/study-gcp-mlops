"""Mappers — Pydantic schema (HTTP) ↔ domain model conversions.

Phase D-3 added explicit mapping so handlers don't carry conversion logic
inline. Each domain → schema function lives next to its endpoint
(``search_mapper`` for /search and /rag).
"""

from .search_mapper import (
    rag_request_to_search_input,
    search_request_to_input,
    search_result_item_to_schema,
    to_rag_response,
    to_search_response,
)

__all__ = [
    "rag_request_to_search_input",
    "search_request_to_input",
    "search_result_item_to_schema",
    "to_rag_response",
    "to_search_response",
]
