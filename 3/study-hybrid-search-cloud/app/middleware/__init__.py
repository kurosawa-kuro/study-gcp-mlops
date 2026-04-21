"""ASGI middleware for the FastAPI app."""

from api.middleware.request_logging import RequestLoggingMiddleware

__all__ = ["RequestLoggingMiddleware"]
