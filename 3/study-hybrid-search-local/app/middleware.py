"""
FastAPI middleware for request context propagation and error handling.
"""

import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from common.core.logging import RequestContextVar, get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set up request context (request_id, timing, etc)."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = RequestContextVar.generate_request_id()
        else:
            RequestContextVar.set("request_id", request_id)

        # Extract user ID if available
        user_id = request.headers.get("X-User-ID")
        if user_id:
            RequestContextVar.set("user_id", user_id)

        # Record start time
        start_time = time.time()

        response: Response | None = None
        try:
            response = await call_next(request)
        finally:
            # Calculate elapsed time
            elapsed_time = time.time() - start_time

            # Log request completion (only if response exists)
            if response is not None:
                logger.info(
                    f"{request.method} {request.url.path} - {response.status_code}",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "elapsed_time_ms": round(elapsed_time * 1000, 2),
                        "user_id": user_id or "anonymous",
                    },
                )

        # Add request ID to response headers (if response exists)
        if response is not None:
            response.headers["X-Request-ID"] = request_id
        return response


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    request_id = RequestContextVar.get("request_id", "unknown")
    user_id = RequestContextVar.get("user_id", "anonymous")

    # Log the exception with full context
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "user_id": user_id,
            "exception_type": type(exc).__name__,
        },
    )

    # Determine status code based on exception type
    status_code = 500
    message = "Internal server error"

    if isinstance(exc, TimeoutError):
        status_code = 504
        message = "Request timeout"
    elif isinstance(exc, ConnectionError):
        status_code = 503
        message = "Service unavailable"

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": type(exc).__name__,
                "message": message,
                "request_id": request_id,
            }
        },
    )
