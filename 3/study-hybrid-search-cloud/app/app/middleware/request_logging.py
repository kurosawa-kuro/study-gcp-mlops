"""Backward-compatible import path for the request logging middleware."""

from app.api.middleware.request_logging import RequestLoggingMiddleware

__all__ = ["RequestLoggingMiddleware"]
