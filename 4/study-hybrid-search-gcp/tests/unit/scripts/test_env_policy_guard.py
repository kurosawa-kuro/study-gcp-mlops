from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_meili_identity_token_is_always_enabled_in_runtime_and_deploy_paths() -> None:
    runtime_tf = _read("infra/terraform/modules/runtime/main.tf")
    deploy_api = _read("scripts/deploy/api_local.py")
    workflow = _read(".github/workflows/deploy-api.yml")

    assert 'name  = "MEILI_REQUIRE_IDENTITY_TOKEN"' in runtime_tf
    assert 'value = "true"' in runtime_tf
    assert "MEILI_REQUIRE_IDENTITY_TOKEN=true" in deploy_api
    assert "MEILI_REQUIRE_IDENTITY_TOKEN=true" in workflow
    assert "MEILI_REQUIRE_IDENTITY_TOKEN=false" not in runtime_tf
    assert "MEILI_REQUIRE_IDENTITY_TOKEN=false" not in deploy_api
    assert "MEILI_REQUIRE_IDENTITY_TOKEN=false" not in workflow


def test_search_api_is_public_in_deploy_paths() -> None:
    runtime_tf = _read("infra/terraform/modules/runtime/main.tf")
    deploy_api = _read("scripts/deploy/api_local.py")
    workflow = _read(".github/workflows/deploy-api.yml")

    assert 'member   = "allUsers"' in runtime_tf
    assert "--allow-unauthenticated" in deploy_api
    assert "--allow-unauthenticated" in workflow
    assert "--no-allow-unauthenticated" not in deploy_api
    assert "--no-allow-unauthenticated" not in workflow


def test_meilisearch_service_is_not_public_invoker() -> None:
    meili_tf = _read("infra/terraform/modules/meilisearch/main.tf")
    assert "allUsers" not in meili_tf
