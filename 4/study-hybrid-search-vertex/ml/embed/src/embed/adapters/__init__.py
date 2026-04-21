"""Embedding-job concrete adapters (BigQuery writer / property text reader)."""

from .embedding_writer import create_embedding_store, create_property_text_repository

__all__ = [
    "create_embedding_store",
    "create_property_text_repository",
]
