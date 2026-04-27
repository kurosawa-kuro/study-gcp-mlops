from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import ops_router
from scripts.ops.destroy_check import Finding

ops_router_module = importlib.import_module("app.api.routers.ops_router")


def test_destroy_check_returns_summary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        ops_router_module,
        "collect_findings",
        lambda project_id, region, vertex_location: [
            Finding(label="GKE clusters", severity="OK", items=()),
            Finding(label="Managed residual buckets", severity="WARN", items=("mlops-dev-a-tfstate",)),
            Finding(label="Cloud Run services", severity="FAIL", items=("meili-search",)),
        ],
    )
    app = FastAPI()
    app.include_router(ops_router)
    client = TestClient(app)

    res = client.get("/ops/destroy-check")

    assert res.status_code == 200
    body = res.json()
    assert body["project_id"] == "mlops-dev-a"
    assert body["summary"] == {"ok": 1, "warn": 1, "fail": 1, "error": 0, "passed": False}
    assert body["findings"][1]["items"] == ["mlops-dev-a-tfstate"]
