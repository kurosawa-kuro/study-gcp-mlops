"""Backward-compatible wrapper for embedding writer factories."""

from ml.data.loaders.embedding_writer import create_embedding_store, create_property_text_repository

__all__ = ["create_embedding_store", "create_property_text_repository"]
