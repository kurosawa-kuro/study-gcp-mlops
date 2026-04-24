from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_setup_scripts_use_local_and_ci_import_paths() -> None:
    deploy_all = _read("scripts/local/setup/deploy_all.py")
    destroy_all = _read("scripts/local/setup/destroy_all.py")

    assert "from scripts.ci.sync_dataform import main as sync_dataform_main" in deploy_all
    assert "from scripts.local.deploy.api_gke import main as deploy_api_main" in deploy_all
    assert (
        "from scripts.local.deploy.kserve_models import main as deploy_kserve_models_main"
        in deploy_all
    )
    assert "from scripts.local.setup.tf_bootstrap import main as tf_bootstrap_main" in deploy_all
    assert "from scripts.local.setup.tf_init import main as tf_init_main" in deploy_all
    assert "from scripts.local.setup.tf_plan import main as tf_plan_main" in deploy_all
    assert "from scripts.setup." not in deploy_all

    assert (
        "from scripts.local.setup.seed_minimal_clean import main as seed_clean_main" in destroy_all
    )
    assert "from scripts.setup.seed_minimal_clean" not in destroy_all


def test_setup_scripts_target_dev_terraform_environment() -> None:
    deploy_all = _read("scripts/local/setup/deploy_all.py")
    destroy_all = _read("scripts/local/setup/destroy_all.py")
    tf_init = _read("scripts/local/setup/tf_init.py")
    tf_plan = _read("scripts/local/setup/tf_plan.py")

    expected = (
        'Path(__file__).resolve().parents[3] / "infra" / "terraform" / "environments" / "dev"'
    )
    assert expected in deploy_all
    assert expected in destroy_all
    assert expected in tf_init
    assert expected in tf_plan


def test_api_deploy_targets_gke_kserve_boundaries() -> None:
    api_gke = _read("scripts/local/deploy/api_gke.py")

    assert "kubectl" in api_gke
    assert "rollout" in api_gke
    assert "search-api" in api_gke
    # GKE 版は Cloud Run 特有の flag を使わない
    assert "--allow-unauthenticated" not in api_gke
    assert "gcloud run deploy" not in api_gke


def test_kserve_models_script_uses_kubectl_patch() -> None:
    kserve_models = _read("scripts/local/deploy/kserve_models.py")

    assert "kubectl" in kserve_models
    assert "inferenceservice" in kserve_models
    assert "property-encoder" in kserve_models
    assert "property-reranker" in kserve_models


def test_makefile_has_gke_compatible_ops_targets() -> None:
    makefile = _read("Makefile")

    assert "deploy-all:" in makefile
    assert "destroy-all:" in makefile
