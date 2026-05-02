"""Phase 7 workflow contracts.

These tests do not prove that GCP resources are healthy. They prove that the
*workflow wiring* still encodes the project goal:

1. ``deploy-all`` remains a one-shot PDCA path.
2. seed data is written before Feature View sync.
3. runtime ConfigMap overlay receives live Terraform outputs for VVS/FOS.

Without these checks the repo tends to regress into "manual recovery steps
after deploy-all", which is exactly the failure mode Wave 2 exposed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import configmap_overlay
from scripts.setup import deploy_all, destroy_all

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_deploy_all_step_sequence_pins_one_shot_pdca_contract() -> None:
    steps = deploy_all._steps()
    names = [step.name for step in steps]

    assert names == [
        "tf-bootstrap",
        "tf-init",
        "recover-wif",
        "sync-dataform",
        "tf-plan",
        "tf-apply",
        "seed-lgbm-model",
        "seed-test",
        "trigger-fv-sync",
        "apply-manifests",
        "overlay-configmap",
        "deploy-api",
    ], "deploy-all drifted from the Phase 7 one-shot PDCA path"
    assert [step.number for step in steps] == list(range(1, 13))
    assert names.index("seed-test") < names.index("trigger-fv-sync")
    assert names.index("trigger-fv-sync") < names.index("apply-manifests")
    assert names.index("overlay-configmap") < names.index("deploy-api")


def test_configmap_overlay_injects_live_vertex_outputs(monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ID", "mlops-test")
    monkeypatch.setenv("REGION", "asia-northeast1")
    monkeypatch.setenv("MODELS_BUCKET", "mlops-test-models")

    captured: dict[str, str] = {}

    def _fake_generate(*, project_id: str, models_bucket: str, meili_base_url: str, **kwargs: str):
        captured["project_id"] = project_id
        captured["models_bucket"] = models_bucket
        captured["meili_base_url"] = meili_base_url
        captured.update(kwargs)
        return {"project_id": project_id}

    with (
        patch.object(
            configmap_overlay,
            "_resolve_meili_url",
            return_value="https://meili.example.run.app",
        ),
        patch.object(
            configmap_overlay,
            "_terraform_output_map",
            return_value={
                "vector_search_index_endpoint_id": "projects/x/locations/r/indexEndpoints/123",
                "vector_search_deployed_index_id": "property_embeddings_v1",
                "vertex_feature_online_store_id": "store-a",
                "vertex_feature_view_id": "view-a",
                "vertex_feature_online_store_endpoint": "store.example.com",
            },
        ),
        patch.object(configmap_overlay, "generate_configmap_data", side_effect=_fake_generate),
        patch.object(configmap_overlay, "render_configmap_yaml", return_value="apiVersion: v1\n"),
        patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["kubectl"], returncode=0),
        ) as run_mock,
    ):
        assert configmap_overlay.main() == 0

    assert captured == {
        "project_id": "mlops-test",
        "models_bucket": "mlops-test-models",
        "meili_base_url": "https://meili.example.run.app",
        "vertex_vector_search_index_endpoint_id": "projects/x/locations/r/indexEndpoints/123",
        "vertex_vector_search_deployed_index_id": "property_embeddings_v1",
        "vertex_feature_online_store_id": "store-a",
        "vertex_feature_view_id": "view-a",
        "vertex_feature_online_store_endpoint": "store.example.com",
    }
    run_mock.assert_called_once()


def test_run_all_core_recipe_pins_canonical_validation_path() -> None:
    makefile = _read("Makefile")
    expected_lines = [
        "$(MAKE) check-layers",
        "$(MAKE) seed-test",
        "$(MAKE) sync-meili",
        "$(MAKE) ops-train-now",
        "$(MAKE) ops-livez",
        "$(MAKE) ops-search",
        "$(MAKE) ops-search-components",
        "$(MAKE) ops-vertex-vector-search-smoke",
        "$(MAKE) ops-vertex-feature-group",
        "$(MAKE) ops-feedback",
        "$(MAKE) ops-ranking",
        "$(MAKE) ops-label-seed",
        "$(MAKE) ops-daily",
        "$(MAKE) ops-accuracy-report",
    ]
    positions = [makefile.index(line) for line in expected_lines]
    assert positions == sorted(positions), "run-all-core drifted from the canonical validation order"
    assert "verify-all: ## Alias of run-all-core" in makefile
    assert "$(MAKE) run-all-core" in makefile


def test_ops_vertex_all_includes_vvs_and_feature_view_checks() -> None:
    makefile = _read("Makefile")
    target_line = (
        "ops-vertex-all: ops-vertex-models-list ops-vertex-pipeline-status "
        "ops-vertex-explain ops-vertex-monitoring "
        "ops-vertex-vector-search-smoke ops-vertex-feature-group"
    )
    assert target_line in makefile, "ops-vertex-all must include VVS + Feature View smoke"


def test_destroy_all_keeps_pdca_reproducibility_guards() -> None:
    assert "module.gke.google_container_cluster.hybrid_search" in destroy_all.PROTECTED_TARGETS
    assert "module.data.google_bigquery_table.property_features_daily" in (
        destroy_all.PROTECTED_TARGETS
    )
    assert destroy_all.KSERVE_MODULE_TARGET == "module.kserve"

    source = _read("scripts/setup/destroy_all.py")
    assert "state list is empty — nothing to destroy" in source
    assert "seed-test-clean" in source
    assert "undeploy Vertex endpoint deployed_models" in source
    assert "terraform destroy -target=module.kserve" in source
    assert "terraform destroy -auto-approve (本体)" in source


def test_canonical_docs_describe_workflow_contract_goals() -> None:
    spec = _read("docs/architecture/01_仕様と設計.md")
    validation = _read("docs/runbook/04_検証.md")
    operations = _read("docs/runbook/05_運用.md")
    catalog = _read("docs/architecture/03_実装カタログ.md")

    for required in (
        "## 8. Workflow Contract が守るべきゴール",
        "G-W1. PDCA は `deploy-all -> run-all -> destroy-all` の 1 本線で完結する",
        "G-W4. canonical serving path を検証本線に含める",
    ):
        assert required in spec, f"spec lost workflow contract requirement: {required}"

    for required in (
        "G3 | **3 種コンポーネント (load-bearing)**",
        "G4 | **canonical semantic / feature path**",
        "make ops-vertex-vector-search-smoke",
        "scripts.ops.vertex.feature_group",
    ):
        assert required in validation, f"validation guide lost canonical gate: {required}"

    for required in (
        "## 1. PDCA メインフロー (`make deploy-all` → `make run-all` → `make destroy-all`)",
        "make run-all           # = run-all-core + リアルタイム監視 (ops-run-all-monitor)",
        "ops-vertex-vector-search-smoke",
        "ops-vertex-feature-group",
    ):
        assert required in operations, f"operations guide drifted from workflow contract: {required}"

    for required in (
        "tests/integration/workflow/",
        "tests/e2e/",
        "setup/deploy_all.py",
        "ops/vertex/{models_list,pipeline_status,vector_search,feature_group,monitoring,explain}.py",
    ):
        assert required in catalog, f"implementation catalog drifted from workflow/test inventory: {required}"
