"""HTML template handlers for ``/`` ``/metrics`` ``/data``.

The router needs the ``Jinja2Templates`` instance constructed against the
app root, so this module exposes a builder rather than a static router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_container
from app.composition_root import Container


def build_ui_router(*, app_root: Path) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=str(app_root / "templates"))

    @router.get("/")
    def ui(request: Request) -> object:
        search_payload = {
            "query": "渋谷 1LDK",
            "filters": {
                "max_rent": 220000,
                "layout": "1LDK",
                "max_walk_min": 12,
                "pet_ok": True,
                "max_age": 20,
            },
            "top_k": 20,
        }
        feedback_payload = {
            "request_id": "demo-request-id",
            "property_id": "1001",
            "action": "click",
        }
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "active": "predict",
                "search_payload": search_payload,
                "feedback_payload": feedback_payload,
            },
        )

    @router.get("/metrics")
    def metrics_ui(
        request: Request,
        container: Annotated[Container, Depends(get_container)],
    ) -> object:
        settings = container.settings
        payload = {
            "service": "phase7-gke-kserve-api",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "project_id": settings.project_id,
            "enable_search": settings.enable_search,
            "enable_rerank": settings.enable_rerank,
            "kserve_encoder_url": settings.kserve_encoder_url,
            "kserve_reranker_url": settings.kserve_reranker_url,
            "model_path": container.model_path,
        }
        return templates.TemplateResponse(
            request,
            "metrics.html",
            {"active": "metrics", "metrics": payload},
        )

    @router.get("/data")
    def data_ui(request: Request) -> object:
        rows = [
            {"key": "search_payload", "value": '{"query":"渋谷 1LDK","top_k":20}'},
            {"key": "feedback_payload", "value": '{"request_id":"...","action":"click"}'},
            {"key": "kserve_encoder", "value": "settings.kserve_encoder_url"},
            {"key": "kserve_reranker", "value": "settings.kserve_reranker_url"},
        ]
        return templates.TemplateResponse(
            request,
            "data.html",
            {"active": "data", "columns": ["key", "value"], "rows": rows, "total": len(rows)},
        )

    return router
