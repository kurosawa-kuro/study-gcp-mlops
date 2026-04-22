"""
Logging configuration for structured logging across the application.

Sets up JSON-formatted logs for production use with proper context propagation.
"""

import json
import logging
import logging.config
import os
import sys
import uuid
from typing import Any

# Define the logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "common.core.logging.JSONFormatter",
        },
        "console": {
            "format": "[%(levelname)s] %(name)s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "json" if os.getenv("LOG_FORMAT") == "json" else "console",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": os.getenv("LOG_LEVEL", "INFO"),
        "handlers": ["console"],
    },
    "loggers": {
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "src": {
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "handlers": ["console"],
            "propagate": True,
        },
    },
}


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Merge extra fields
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """Initialize logging configuration."""
    logging.config.dictConfig(LOGGING_CONFIG)


def get_logger(name: str) -> logging.LoggerAdapter:
    """Get a logger with request context support."""
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, {})


class RequestContextVar:
    """Thread-local storage for request context (request_id, user_id, etc)."""

    _local_data: dict[str, Any] = {}

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Store a value in request context."""
        cls._local_data[key] = value

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Retrieve a value from request context."""
        return cls._local_data.get(key, default)

    @classmethod
    def clear(cls) -> None:
        """Clear all request context."""
        cls._local_data.clear()

    @classmethod
    def generate_request_id(cls) -> str:
        """Generate or retrieve request ID."""
        request_id = cls.get("request_id")
        if request_id is None:
            request_id = str(uuid.uuid4())
            cls.set("request_id", request_id)
        return request_id
