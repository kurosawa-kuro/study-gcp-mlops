"""Phase 7 workflow contracts.

These tests do not prove that GCP resources are healthy. They prove that the
*workflow wiring* still encodes the project goal:

1. ``deploy-all`` remains a one-shot PDCA path.
2. seed data is written before Feature View sync.
3. runtime ConfigMap overlay receives live Terraform outputs for VVS/FOS.
4. canonical lexical / semantic / feature lanes are all established by deploy-all.
5. **Cloud Composer は Phase 7 = canonical 起点で本実装** され、3 本 DAG が
   本線 retrain schedule を担う (Vertex `PipelineJobSchedule` 完全撤去 +
   Cloud Scheduler / Eventarc / Cloud Function 軽量経路は smoke / manual 専用
   へ格下げ済 = §3.6 カニバリ NG 防止)。

Without these checks the repo tends to regress into "manual recovery steps
after deploy-all", which is exactly the failure mode Wave 2 exposed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from unittest.mock import patch

from app.composition_root import ContainerBuilder
from app.services.noop_adapters import (
    NoopDataCatalogReader,
    NoopFeedbackRecorder,
    NoopRankingLogPublisher,
    NoopRetrainQueries,
)
from app.settings import ApiSettings
from scripts.deploy import composer_deploy_dags, configmap_overlay
from scripts.setup import deploy_all, destroy_all

REPO_ROOT = Path(__file__).resolve().parents[3]
DAGS_DIR = REPO_ROOT / "pipeline" / "dags"
COMPOSER_MODULE_DIR = REPO_ROOT / "infra" / "terraform" / "modules" / "composer"
DAG_FILES = ("daily_feature_refresh.py", "retrain_orchestration.py", "monitoring_validation.py")


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
        "sync-meili",
        "backfill-vvs",
        "trigger-fv-sync",
        "apply-manifests",
        "overlay-configmap",
        "composer-deploy-dags",
        "deploy-api",
    ], "deploy-all drifted from the Phase 7 one-shot PDCA path"
    assert [step.number for step in steps] == list(range(1, 16))
    assert names.index("seed-test") < names.index("sync-meili")
    assert names.index("seed-test") < names.index("trigger-fv-sync")
    assert names.index("sync-meili") < names.index("backfill-vvs")
    assert names.index("backfill-vvs") < names.index("trigger-fv-sync")
    assert names.index("trigger-fv-sync") < names.index("apply-manifests")
    assert names.index("overlay-configmap") < names.index("composer-deploy-dags")
    assert names.index("composer-deploy-dags") < names.index("deploy-api")


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


def test_local_boot_contract_does_not_require_adc_when_search_disabled(monkeypatch) -> None:
    settings = ApiSettings(
        project_id="mlops-test",
        enable_search=False,
        enable_rerank=False,
    )

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("local boot contract must not touch external GCP clients")

    monkeypatch.setattr(ContainerBuilder, "_bigquery", _forbidden)
    monkeypatch.setattr("app.container.infra.PubSubPublisher", _forbidden)
    monkeypatch.setattr("app.container.infra.PubSubRankingLogPublisher", _forbidden)
    monkeypatch.setattr("app.container.infra.PubSubFeedbackRecorder", _forbidden)

    container = ContainerBuilder(settings).build()

    assert container.candidate_retriever is None
    assert container.encoder_client is None
    assert container.feature_fetcher is None
    assert container.retrain_trigger_publisher is None
    assert isinstance(container.retrain_queries, NoopRetrainQueries)
    assert isinstance(container.data_catalog_service._reader, NoopDataCatalogReader)
    assert isinstance(container.ranking_log_publisher, NoopRankingLogPublisher)
    assert isinstance(container.feedback_recorder, NoopFeedbackRecorder)


def test_run_all_core_recipe_pins_canonical_validation_path() -> None:
    makefile = _read("Makefile")
    expected_lines = [
        "$(MAKE) check-layers",
        "$(MAKE) seed-test",
        "$(MAKE) sync-meili",
        "$(MAKE) ops-train-now",
        "$(MAKE) ops-train-wait",
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
    assert positions == sorted(positions), (
        "run-all-core drifted from the canonical validation order"
    )
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
        "FastAPI boot / import / `/livez` 200 は ADC なし local でも成立する",
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
        assert required in operations, (
            f"operations guide drifted from workflow contract: {required}"
        )

    for required in (
        "tests/integration/workflow/",
        "tests/e2e/",
        "setup/deploy_all.py",
        "ops/vertex/{models_list,pipeline_status,vector_search,feature_group,monitoring,explain}.py",
    ):
        assert required in catalog, (
            f"implementation catalog drifted from workflow/test inventory: {required}"
        )


# =========================================================================
# Cloud Composer (W2-4) workflow contracts — Phase 7 canonical orchestration.
#
# 以下の test 群は live 検証 (`make deploy-all` → `make composer-deploy-dags` →
# Airflow UI) より **前** に **DAG / Terraform / IAM / Make / scripts の
# wiring が崩れていないか** を pin する。Stage 2 Stage 3 の live で「3 DAG が
# parse できない」「composer SA に role 不足」「PipelineJobSchedule が再生」
# 「DAG が存在しない script を呼ぶ」等の事故を未然に防ぐ目的。
#
# 詳細仕様は docs/architecture/01_仕様と設計.md §3 / §3.6 と
# docs/tasks/TASKS_ROADMAP.md §4.7 を参照。
# =========================================================================


def test_composer_module_exists_with_required_files() -> None:
    """Phase 7 W2-4 Stage 1: `infra/terraform/modules/composer/` 必須 4 ファイル。"""
    assert COMPOSER_MODULE_DIR.is_dir(), "infra/terraform/modules/composer/ is missing"
    for required in ("main.tf", "variables.tf", "outputs.tf", "versions.tf"):
        assert (COMPOSER_MODULE_DIR / required).is_file(), f"composer module missing {required}"


def test_composer_module_uses_gen3_image_with_enable_flag_gate() -> None:
    """Composer 環境は Gen 3 image + `enable_composer` flag で count gate。"""
    main_tf = _read("infra/terraform/modules/composer/main.tf")
    assert 'image_version = "composer-3-airflow-' in main_tf, (
        "composer module must use composer-3-airflow-* (Gen 3 mandatory)"
    )
    assert "count    = var.enable_composer ? 1 : 0" in main_tf, (
        "composer environment must be count-gated by var.enable_composer"
    )
    # Vertex resource ID を env_variables 経由で worker に伝搬している
    for required_env in (
        "PROJECT_ID",
        "REGION",
        "VERTEX_LOCATION",
        "PIPELINE_ROOT_BUCKET",
        "VERTEX_VECTOR_SEARCH_INDEX_RESOURCE_NAME",
        "VERTEX_FEATURE_ONLINE_STORE_ID",
        "VERTEX_FEATURE_VIEW_ID",
    ):
        assert required_env in main_tf, (
            f"composer env_variables must surface {required_env} (DAG worker reads via os.environ)"
        )


def test_composer_module_outputs_dag_bucket_and_airflow_uri() -> None:
    outputs_tf = _read("infra/terraform/modules/composer/outputs.tf")
    for required_output in (
        'output "dag_bucket"',
        'output "airflow_uri"',
        'output "environment_name"',
    ):
        assert required_output in outputs_tf, (
            f"composer module outputs.tf missing {required_output}"
        )


def test_composer_module_wired_into_dev_environment_with_correct_depends_on() -> None:
    """`environments/dev/main.tf` で `module "composer"` が iam / data / vector_search /
    vertex に depends_on で繋がっていること (apply 順序 = Stage 1 contract)。"""
    main_tf = _read("infra/terraform/environments/dev/main.tf")
    assert 'module "composer" {' in main_tf, "module composer not wired into dev environment"
    assert 'source = "../../modules/composer"' in main_tf
    # composer は iam (sa-composer) / data (pipeline_root_bucket) / vector_search /
    # vertex (FOS) の outputs を消費するため depends_on で順序を pin
    composer_block_match = re.search(r'module "composer" \{(.+?)\n\}\n', main_tf, flags=re.DOTALL)
    assert composer_block_match is not None, "could not parse module composer block"
    block = composer_block_match.group(1)
    for required_dep in ("module.iam", "module.data", "module.vector_search", "module.vertex"):
        assert required_dep in block, (
            f"module composer must depends_on {required_dep} (output / apply 順序保証)"
        )


def test_dev_environment_has_composer_variables_and_outputs() -> None:
    variables_tf = _read("infra/terraform/environments/dev/variables.tf")
    outputs_tf = _read("infra/terraform/environments/dev/outputs.tf")

    for required_var in (
        'variable "enable_composer"',
        'variable "composer_environment_name"',
        'variable "pipeline_template_gcs_path"',
    ):
        assert required_var in variables_tf, f"dev environment missing variable {required_var}"

    for required_output in (
        'output "composer_dag_bucket"',
        'output "composer_airflow_uri"',
        'output "composer_environment_name"',
    ):
        assert required_output in outputs_tf, (
            f"dev environment outputs.tf missing {required_output} "
            "(composer_deploy_dags consumes composer_dag_bucket)"
        )


def test_iam_module_provisions_sa_composer_with_required_roles() -> None:
    """W2-4 Stage 1 IAM 契約: `sa-composer` SA + 4 role + outputs map entry。"""
    iam_main = _read("infra/terraform/modules/iam/main.tf")
    iam_outputs = _read("infra/terraform/modules/iam/outputs.tf")

    assert 'resource "google_service_account" "composer" {' in iam_main
    assert 'account_id   = "sa-composer"' in iam_main

    for required_role in (
        '"roles/composer.worker"',
        '"roles/aiplatform.user"',
        '"roles/bigquery.jobUser"',
        '"roles/bigquery.dataViewer"',
        '"roles/run.invoker"',
    ):
        assert required_role in iam_main, (
            f"sa-composer must have {required_role} (Phase 7 W2-4 Stage 1 contract)"
        )

    # deployer SA に composer.admin (terraform apply で composer 環境を作成する権限)
    assert "google_project_iam_member" in iam_main and '"roles/composer.admin"' in iam_main, (
        "github_deployer must have roles/composer.admin to provision Composer env"
    )

    # outputs map に composer entry
    assert "composer          = google_service_account.composer" in iam_outputs, (
        "iam module outputs.service_accounts map must include composer entry"
    )


def test_tf_apply_stage1_targets_includes_module_composer() -> None:
    """`module.composer` は `TF_APPLY_STAGE1_TARGETS` に含まれること
    (kserve provider 初期化前に Composer 環境を立てる)。"""
    assert "module.composer" in deploy_all.TF_APPLY_STAGE1_TARGETS, (
        "module.composer missing from TF_APPLY_STAGE1_TARGETS — apply 順序が崩れる"
    )


def test_composer_deploy_dags_step_inserted_between_overlay_and_deploy_api() -> None:
    """deploy_all の `composer-deploy-dags` step は `overlay-configmap` 後 /
    `deploy-api` 前に固定 — DAG GCS upload は ConfigMap overlay 後 (env が解決
    済み) であり、search-api rollout 前に走らせて DAG が trigger 可能な状態
    で deploy 完了させる契約。"""
    steps = deploy_all._steps()
    names = [step.name for step in steps]

    assert "composer-deploy-dags" in names, "composer-deploy-dags step missing from deploy_all"
    composer_idx = names.index("composer-deploy-dags")
    overlay_idx = names.index("overlay-configmap")
    deploy_api_idx = names.index("deploy-api")

    assert overlay_idx < composer_idx < deploy_api_idx, (
        "composer-deploy-dags must be between overlay-configmap and deploy-api "
        f"(got overlay={overlay_idx}, composer={composer_idx}, deploy-api={deploy_api_idx})"
    )

    # `composer-deploy-dags` step の callable は `_run_composer_deploy_dags` で、
    # 中で `composer_deploy_dags.main()` を呼ぶ wrapper (deploy_all 規約)。
    composer_step = next(s for s in steps if s.name == "composer-deploy-dags")
    assert composer_step.run is deploy_all._run_composer_deploy_dags, (
        "composer-deploy-dags step.run must be _run_composer_deploy_dags wrapper"
    )


def test_composer_deploy_dags_early_returns_when_disabled(monkeypatch) -> None:
    """`enable_composer=false` → terraform output `composer_dag_bucket` 空 →
    `composer_deploy_dags.main()` は rc=0 で skip (Stage 1/Stage 2 互換契約)。"""
    import json as _json

    def _fake_run(cmd, capture=False, check=False):
        proc = subprocess.CompletedProcess(cmd, returncode=0, stdout=_json.dumps({}))
        return proc

    monkeypatch.setattr(composer_deploy_dags, "run", _fake_run)
    assert composer_deploy_dags.main() == 0


def test_makefile_exposes_composer_deploy_dags_and_smoke_targets() -> None:
    """`make composer-deploy-dags` / `ops-composer-trigger` / `ops-composer-list-runs`
    が `.PHONY` に登録され、recipe を持つこと。"""
    makefile = _read("Makefile")

    for required_target in (
        "composer-deploy-dags",
        "ops-composer-trigger",
        "ops-composer-list-runs",
    ):
        assert f"{required_target}:" in makefile, f"Make target {required_target} missing"
        # .PHONY 経由でも宣言されている
        assert required_target in makefile.split(".PHONY")[1], (
            f"{required_target} must appear in .PHONY"
        )

    assert "uv run python -m scripts.deploy.composer_deploy_dags" in makefile, (
        "composer-deploy-dags recipe must invoke scripts.deploy.composer_deploy_dags"
    )
    assert "gcloud composer environments run" in makefile, (
        "ops-composer-trigger / list-runs must shell out to gcloud composer"
    )
    assert "COMPOSER_ENV  ?= " in makefile, (
        "Makefile must define COMPOSER_ENV var (default for ops-composer-* targets)"
    )


def test_dag_files_pin_canonical_schedule_and_dag_id() -> None:
    """3 本 DAG の schedule + dag_id + catchup=False が canonical (本実装契約)。

    schedule の段差: daily_feature_refresh (16:00 UTC = 01:00 JST) →
    retrain_orchestration (19:00 UTC = 04:00 JST、3h 後) →
    monitoring_validation (19:30 UTC = 04:30 JST、+30min)。
    本線 retrain schedule は Composer DAG のみが担う (Cloud Scheduler は smoke 用)。
    """
    expected_schedule = {
        "daily_feature_refresh": "0 16 * * *",
        "retrain_orchestration": "0 19 * * *",
        "monitoring_validation": "30 19 * * *",
    }
    for dag_file in DAG_FILES:
        text = (DAGS_DIR / dag_file).read_text(encoding="utf-8")
        dag_id = dag_file.removesuffix(".py")
        assert f'dag_id="{dag_id}"' in text, f"{dag_file}: dag_id literal mismatch"
        assert f'schedule="{expected_schedule[dag_id]}"' in text, (
            f"{dag_file}: schedule must be {expected_schedule[dag_id]} (canonical 段差)"
        )
        assert "catchup=False" in text, f"{dag_file}: catchup=False is mandatory"


def test_dag_files_avoid_kfp_2_16_module_level_compile_import() -> None:
    """KFP 2.16 互換 issue (TASKS_ROADMAP §4.8 W2-9) 回避契約。

    `pipeline.workflow.compile` の module-level `@dsl.pipeline` decorator は
    KFP 2.16 で TypeError を起こすため、DAG file が `from pipeline.workflow.
    compile import ...` すると Composer scheduler が DAG parse 失敗する。
    `python -m pipeline.workflow.compile --submit ...` を BashOperator 経由で
    叩くこと (= `make ops-train-now` と同一の live 実証済 invocation path)。
    """
    for dag_file in DAG_FILES:
        text = (DAGS_DIR / dag_file).read_text(encoding="utf-8")
        assert "from pipeline.workflow.compile" not in text, (
            f"{dag_file} must NOT import pipeline.workflow.compile directly "
            "(KFP 2.16 互換 issue で module load 段で TypeError)"
        )


def test_retrain_dag_is_canonical_retrain_trigger() -> None:
    """`retrain_orchestration` DAG は本線 retrain schedule を担う唯一の経路。

    docs/01 §3.6 カニバリ NG: 同一 retrain を Composer DAG + Cloud Scheduler +
    Vertex `PipelineJobSchedule` の複数経路で起動しないこと。本 test は DAG 側
    (= Composer 経路) が `pipeline.workflow.compile --submit` を本線として
    呼んでいることを pin。
    """
    text = (DAGS_DIR / "retrain_orchestration.py").read_text(encoding="utf-8")
    assert "python -m pipeline.workflow.compile" in text
    assert "--target train" in text
    assert "--submit" in text
    # check_retrain → submit → wait → promote の依存チェーンが宣言されている
    for required_task in (
        "check_retrain",
        "submit_train_pipeline",
        "wait_train_succeeded",
        "promote_reranker",
    ):
        assert f'task_id="{required_task}"' in text, f"retrain DAG missing task {required_task}"


def test_dag_files_call_only_existing_scripts() -> None:
    """DAG が呼ぶ `python -m scripts.*` / `python -m pipeline.*` のターゲットが
    実ファイルに解決すること (= live で「No module named ...」事故防止)。"""
    expected_modules = {
        "scripts.infra.feature_view_sync": "scripts/infra/feature_view_sync.py",
        "scripts.setup.backfill_vector_search_index": "scripts/setup/backfill_vector_search_index.py",
        "scripts.ops.check_retrain": "scripts/ops/check_retrain.py",
        "scripts.ops.vertex.pipeline_wait": "scripts/ops/vertex/pipeline_wait.py",
        "scripts.ops.promote": "scripts/ops/promote.py",
        "scripts.ops.slo_status": "scripts/ops/slo_status.py",
        "pipeline.workflow.compile": "pipeline/workflow/compile.py",
    }
    all_dag_text = "\n".join(
        (DAGS_DIR / dag_file).read_text(encoding="utf-8") for dag_file in DAG_FILES
    )
    for module_name, file_rel in expected_modules.items():
        if module_name in all_dag_text:
            assert (REPO_ROOT / file_rel).is_file(), (
                f"DAG references python -m {module_name} but {file_rel} is missing"
            )


def test_layers_rules_isolate_pipeline_dags_from_app_imports() -> None:
    """`pipeline/dags/` は `app.*` import 禁止 (Composer worker reparse 軽量化)。"""
    from scripts.ci import layers

    assert "pipeline/dags/" in layers.DIRECTORY_RULES, (
        "pipeline/dags/ DIRECTORY_RULES missing — Composer worker が app.* を import すると重い"
    )
    bans = layers.DIRECTORY_RULES["pipeline/dags/"]
    assert "app" in bans, "pipeline/dags/ must ban `app` import (forbidden imports list)"


def test_no_vertex_pipeline_job_schedule_resource_in_terraform() -> None:
    """カニバリ NG: Vertex `PipelineJobSchedule` は Phase 7 で完全撤去 (docs/01 §3.6)。
    Composer DAG schedule + Vertex `PipelineJobSchedule` の二重起動を防ぐ。"""
    tf_dir = REPO_ROOT / "infra" / "terraform"
    forbidden_patterns = ("google_vertex_ai_pipeline_job_schedule", "PipelineJobSchedule")
    for tf_file in tf_dir.rglob("*.tf"):
        text = tf_file.read_text(encoding="utf-8")
        for forbidden in forbidden_patterns:
            assert forbidden not in text, (
                f"{tf_file.relative_to(REPO_ROOT)} contains forbidden {forbidden!r} "
                "(Phase 7 W2-4 で撤去済、§3.6 カニバリ NG で再導入禁止)"
            )


def test_composer_canonical_doc_section_exists() -> None:
    """docs/01 §3 が「Phase 7 で本実装、後方派生で Phase 6 へ引き算」の wording で
    canonical 起点を宣言していること (Stage 1.1 docs rewrite 結果 pin)。"""
    spec = _read("docs/architecture/01_仕様と設計.md")
    for required in (
        "## 3. Cloud Composer の位置づけ (Phase 7 で本実装、後方派生で Phase 6 へ引き算)",
        "**Phase 7 で本線オーケストレーターとして本実装**",
        "Vertex `PipelineJobSchedule` → **完全撤去**",
        "### 3.6 Phase 7 (= canonical) / 引き算で派生する Phase 6 で禁止する状態",
    ):
        assert required in spec, f"docs/01 §3 lost canonical Composer wording: {required!r}"


def test_feature_view_online_serving_source_is_direct_bigquery() -> None:
    data_tf = _read("infra/terraform/modules/data/main.tf")
    vertex_tf = _read("infra/terraform/modules/vertex/main.tf")
    deploy_all_py = _read("scripts/setup/deploy_all.py")
    assert 'table_id            = "property_features_online_latest"' in data_tf
    assert "depends_on          = [google_bigquery_table.property_features_daily]" in data_tf
    assert (
        "FROM `${var.project_id}.${google_bigquery_dataset.feature_mart.dataset_id}.property_features_daily`"
        in data_tf
    )
    assert 'WHERE event_date = CURRENT_DATE("Asia/Tokyo")' in data_tf
    assert (
        'uri = "bq://${var.project_id}.${var.feature_mart_dataset_id}.property_features_online_latest"'
        in vertex_tf
    )
    assert 'entity_id_columns = ["property_id"]' in vertex_tf
    assert "feature_registry_source {" not in vertex_tf
    assert "TF_APPLY_STAGE1_TARGETS" in deploy_all_py
    assert "wait_for_deployed_index_absent" in deploy_all_py
    assert "wait_until_api_ready" in deploy_all_py
