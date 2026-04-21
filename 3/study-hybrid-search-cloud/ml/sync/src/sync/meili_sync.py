"""Backward-compatible wrapper for the Meilisearch sync job."""

from ml.data.loaders.meili_sync import main, run

__all__ = ["main", "run"]
