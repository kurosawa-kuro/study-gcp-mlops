"""FastAPI hybrid-search API — GKE Pod entrypoint.

This module is the **HTTP server entrypoint only**. DI wiring lives in
``app/composition_root.py``; endpoint logic lives in
``app/api/handlers/``; mapping in ``app/api/mappers/``; business logic in
``app/services/``.

The Pod keeps only retrieval / orchestration concerns. Query embeddings
and rerank scoring are delegated to KServe InferenceService (cluster-local
HTTP) when configured. PMLE technology integrations (RAG, BQML, Agent
Builder, Vertex Vector Search) are wired in as optional adapters per
Phase 6 — see ``ContainerBuilder``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.handlers import (
    build_ui_router,
    feedback_router,
    health_router,
    rag_router,
    retrain_router,
    search_router,
)
from app.api.middleware import RequestLoggingMiddleware
from app.composition_root import ContainerBuilder
from app.services.config import ApiSettings
from ml.common.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the immutable :class:`Container` once and stash on app state."""
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    settings = ApiSettings()
    app.state.container = ContainerBuilder(settings).build()
    yield


def create_app() -> FastAPI:
    configure_logging()
    logger = get_logger("app")
    app = FastAPI(title="gke+kserve-backed hybrid search API", lifespan=lifespan)

    app_root = Path(__file__).resolve().parent
    app.mount("/static", StaticFiles(directory=str(app_root / "static")), name="static")
    app.add_middleware(RequestLoggingMiddleware, logger=logger)

    app.include_router(health_router)
    app.include_router(build_ui_router(app_root=app_root))
    app.include_router(search_router)
    app.include_router(rag_router)
    app.include_router(feedback_router)
    app.include_router(retrain_router)

    return app


app = create_app()
