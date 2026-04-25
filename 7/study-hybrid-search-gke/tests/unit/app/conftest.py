"""Legacy HTTP fixtures adapted to the Phase A DI container model.

Older tests under ``tests/unit/app/`` still expect an app fixture named
``app_with_search_stub`` plus a ``search_client`` built from the full
``create_app()`` entrypoint (middleware included). Phase A moved runtime
state under ``app.state.container``; this conftest now composes a fake
Container via the root fixtures and mirrors a few fields back onto
``app.state`` for backward compatibility with those older assertions.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.handlers import (
    feedback_router,
    health_router,
    rag_router,
    retrain_router,
    search_router,
)
from app.api.middleware import RequestLoggingMiddleware
from app.domain.candidate import Candidate
from app.services.fakes import InMemoryTTLCacheStore
from ml.common.logging import get_logger


@pytest.fixture
def app_with_search_stub(
    fake_container_factory: Callable[..., object],
) -> FastAPI:
    """FastAPI app using the new DI container, with old state mirrors."""
    container = fake_container_factory(
        reranker_client=None,
        model_path=None,
        search_cache=InMemoryTTLCacheStore(default_ttl_seconds=120),
    )
    candidate_retriever = container.candidate_retriever
    if candidate_retriever is not None and hasattr(candidate_retriever, "_candidates"):
        candidate_retriever._candidates = [
            Candidate(
                property_id=f"P-{i:03d}",
                lexical_rank=i,
                semantic_rank=i,
                me5_score=0.9 - 0.1 * i,
                property_features={
                    "rent": 100_000 + 1000 * i,
                    "walk_min": 5 + i,
                    "age_years": 10,
                    "area_m2": 30.0,
                    "ctr": 0.1,
                    "fav_rate": 0.02,
                    "inquiry_rate": 0.01,
                },
            )
            for i in range(1, 4)
        ]
    app = FastAPI()
    app.state.container = container
    app.add_middleware(RequestLoggingMiddleware, logger=get_logger("app"))
    app.include_router(health_router)
    app.include_router(search_router)
    app.include_router(rag_router)
    app.include_router(feedback_router)
    app.include_router(retrain_router)
    # Backward-compat mirrors for older tests that still inspect app.state.*.
    app.state.encoder_client = container.encoder_client
    app.state.candidate_retriever = container.candidate_retriever
    app.state.ranking_log_publisher = container.ranking_log_publisher
    app.state.feedback_recorder = container.feedback_recorder
    app.state.search_cache = container.search_cache
    app.state.settings = container.settings
    app.state.reranker_client = container.reranker_client
    app.state.model_path = container.model_path
    return app


@pytest.fixture
def search_client(app_with_search_stub: FastAPI) -> TestClient:
    with TestClient(app_with_search_stub) as client:
        yield client
