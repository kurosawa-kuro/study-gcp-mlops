"""FastAPI hybrid-search API — GKE Pod entrypoint.

This module is the **HTTP server entrypoint only**. DI wiring lives in
``app/composition_root.py``; endpoint logic lives in
``app/api/handlers/``; mapping in ``app/api/mappers/``; business logic in
``app/services/``.

Route surfaces (kept disjoint to avoid cross-concern collision):

- **App API** — ``/search`` ``/feedback`` ``/rag`` ``/jobs/check-retrain``
- **Probes** — ``/livez`` ``/healthz`` ``/readyz`` (k8s)
- **Prom exposition** — ``/metrics`` (GMP / SLO scrape target)
- **Operator UI** — ``/ui/`` ``/ui/metrics`` ``/ui/data``
  (``/`` redirects to ``/ui/`` so existing bookmarks still resolve)

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
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import Info as MetricInfo

from app.api.handlers import (
    build_ui_router,
    feedback_router,
    health_router,
    model_router,
    rag_router,
    retrain_router,
    search_router,
)
from app.api.middleware import RequestLoggingMiddleware
from app.composition_root import ContainerBuilder
from app.settings import ApiSettings
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

    # App API + probes (no path prefix — these are the public contracts).
    app.include_router(health_router)
    app.include_router(search_router)
    app.include_router(rag_router)
    app.include_router(feedback_router)
    app.include_router(retrain_router)
    app.include_router(model_router)

    # Operator UI is namespaced under /ui/ so /metrics belongs to Prometheus.
    app.include_router(build_ui_router(app_root=app_root), prefix="/ui")

    @app.get("/", include_in_schema=False)
    def _root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/", status_code=308)

    # Prometheus exposition at /metrics. Custom collector emits a `service`
    # label so the SLO module's filter
    # (``metric.label."service"="search-api"`` and ``status=~"2.."``) matches.
    # The default instrumentator metric ships only `handler`/`method`/`status`
    # which leaves the SLO query selecting zero series — see
    # `infra/terraform/modules/slo/main.tf` good/total filter contract.
    _expose_prometheus(app, service_name=os.getenv("OTEL_SERVICE_NAME", "search-api"))

    return app


_REQUEST_LABELS = ("service", "method", "handler", "status")
_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests served by the FastAPI app.",
    labelnames=_REQUEST_LABELS,
)
_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Latency of HTTP requests served by the FastAPI app.",
    labelnames=_REQUEST_LABELS,
)


def _track(service_name: str):  # type: ignore[no-untyped-def]
    """Build a per-request callback that records (service, method, handler, status)."""

    def _record(info: MetricInfo) -> None:
        handler = info.modified_handler or "unhandled"
        raw_status = (
            str(info.response.status_code)
            if info.response is not None and info.response.status_code is not None
            else "0"
        )
        status_class = f"{raw_status[0]}xx" if raw_status and raw_status[0].isdigit() else "unknown"
        _REQUESTS_TOTAL.labels(
            service=service_name,
            method=info.request.method,
            handler=handler,
            status=status_class,
        ).inc()
        _REQUEST_DURATION.labels(
            service=service_name,
            method=info.request.method,
            handler=handler,
            status=status_class,
        ).observe(info.modified_duration)

    return _record


def _expose_prometheus(app: FastAPI, *, service_name: str) -> None:
    instrumentator = Instrumentator(
        excluded_handlers=["/metrics", "/livez", "/healthz", "/readyz"],
    )
    instrumentator.add(_track(service_name))
    instrumentator.instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
        should_gzip=False,
    )


app = create_app()
