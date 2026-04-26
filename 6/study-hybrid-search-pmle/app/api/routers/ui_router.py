"""HTML template handlers for the operator UI.

Routed under ``/ui/`` (see ``app/main.py``) so the bare ``/metrics``
path stays exclusive to Prometheus exposition. UI pages use AJAX
``fetch()`` to call the JSON APIs (``/search``, ``/feedback``,
``/model/metrics``, ``/model/info``); this keeps the UI layer thin and
removable without touching API contracts.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


def build_ui_router(*, app_root: Path) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=str(app_root / "templates"))

    @router.get("/", name="ui-home")
    def ui_home(request: Request) -> object:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "active": "search",
                "default_query": "新宿区西新宿 1LDK",
                "default_max_rent": 150000,
                "default_top_k": 20,
            },
        )

    @router.get("/model/metrics", name="ui-model-metrics")
    def ui_model_metrics(request: Request) -> object:
        return templates.TemplateResponse(
            request,
            "model_metrics.html",
            {"active": "model-metrics", "default_k": 10},
        )

    @router.get("/data", name="ui-data")
    def ui_data(request: Request) -> object:
        return templates.TemplateResponse(
            request,
            "data.html",
            {"active": "data"},
        )

    return router
