"""Compatibility re-export for code still importing from ``app.api.handlers``."""

from app.api.routers import (
    build_ui_router,
    feedback_router,
    health_router,
    model_router,
    rag_router,
    retrain_router,
    search_router,
)

__all__ = [
    "build_ui_router",
    "feedback_router",
    "health_router",
    "model_router",
    "rag_router",
    "retrain_router",
    "search_router",
]
