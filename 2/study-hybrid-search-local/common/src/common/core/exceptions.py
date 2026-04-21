"""Custom exceptions for clearer error handling semantics."""


class MeilisearchTaskError(Exception):
    """Raised when a Meilisearch async task fails or is canceled."""


class MeilisearchTimeoutError(TimeoutError):
    """Raised when waiting for a Meilisearch task exceeds timeout."""


class CacheSyncError(Exception):
    """Raised when cache synchronization fails in a recoverable way."""
