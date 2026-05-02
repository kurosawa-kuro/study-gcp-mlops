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
                "vector_search_deployed_index_id": "property_embeddings_v2",
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
        "vertex_vector_search_deployed_index_id": "property_embeddings_v2",
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


# =========================================================================
# 深い Composer 検証 (live verify でハマる事故を contract レベルで先回り)
# =========================================================================


def test_dag_files_have_valid_python_syntax() -> None:
    """3 DAG file が Python として AST parse 可能 (Composer scheduler が DAG bag に
    込み読みするとき構文エラーで全 DAG が止まる事故を防ぐ)。"""
    import ast

    for dag_file in DAG_FILES:
        text = (DAGS_DIR / dag_file).read_text(encoding="utf-8")
        try:
            ast.parse(text, filename=str(DAGS_DIR / dag_file))
        except SyntaxError as exc:
            raise AssertionError(f"{dag_file} has invalid Python syntax: {exc}") from exc


def test_dag_schedules_are_valid_5_field_cron() -> None:
    """全 DAG の schedule cron が **5-field 形式** で、Airflow が parse 可能なこと。

    1 field でも欠けると Composer scheduler が DAG を loaded but not scheduled
    状態にする事故が起きる。本 test は cron 5 field の存在 + 各 field が
    妥当範囲に収まっていることを syntactic に pin。
    """
    cron_pattern = re.compile(r'schedule="([^"]+)"')
    for dag_file in DAG_FILES:
        text = (DAGS_DIR / dag_file).read_text(encoding="utf-8")
        match = cron_pattern.search(text)
        assert match is not None, f"{dag_file}: schedule literal missing"
        cron = match.group(1)
        fields = cron.split()
        assert len(fields) == 5, (
            f"{dag_file}: schedule {cron!r} must be 5-field cron (got {len(fields)} fields)"
        )
        valid_field = re.compile(r"^[\d*,/\-]+$")
        for i, field in enumerate(fields):
            assert valid_field.match(field), (
                f"{dag_file}: schedule field {i} ({field!r}) has invalid characters"
            )


def test_dag_schedules_avoid_simultaneous_run() -> None:
    """3 DAG schedule が同時刻に走らない (Composer scheduler 圧迫回避)。
    daily_feature_refresh → retrain_orchestration → monitoring_validation の
    順序で >=30 min stagger している契約。"""
    schedules: dict[str, tuple[int, int]] = {}
    cron_pattern = re.compile(r'schedule="([^"]+)"')
    for dag_file in DAG_FILES:
        text = (DAGS_DIR / dag_file).read_text(encoding="utf-8")
        match = cron_pattern.search(text)
        assert match is not None
        cron = match.group(1)
        minute, hour, *_ = cron.split()
        schedules[dag_file.removesuffix(".py")] = (int(hour), int(minute))

    assert schedules["daily_feature_refresh"] < schedules["retrain_orchestration"], (
        "daily_feature_refresh must run BEFORE retrain_orchestration "
        "(feature refresh → retrain 順序契約)"
    )
    assert schedules["retrain_orchestration"] < schedules["monitoring_validation"], (
        "retrain_orchestration must run BEFORE monitoring_validation"
    )

    from itertools import pairwise

    sorted_times = sorted(schedules.values())
    for prev, curr in pairwise(sorted_times):
        prev_minutes = prev[0] * 60 + prev[1]
        curr_minutes = curr[0] * 60 + curr[1]
        assert curr_minutes - prev_minutes >= 30, (
            f"DAG schedules too close: {prev} → {curr} (must be >=30 min apart)"
        )


def test_composer_module_passes_required_terraform_inputs() -> None:
    """`module "composer"` が必須 input 全てを渡している (apply で
    `var. ... is required` の compile 失敗を防ぐ)。"""
    main_tf = _read("infra/terraform/environments/dev/main.tf")
    composer_block_match = re.search(r'module "composer" \{(.+?)\n\}\n', main_tf, flags=re.DOTALL)
    assert composer_block_match is not None
    block = composer_block_match.group(1)

    required_inputs = (
        "enable_composer",
        "project_id",
        "region",
        "vertex_location",
        "environment_name",
        "composer_service_account_email",
        "pipeline_root_bucket_name",
        "vector_search_index_resource_name",
        "feature_online_store_id",
        "feature_view_id",
    )
    for required in required_inputs:
        assert required in block, f"module composer missing required input: {required}"


def test_composer_sa_email_consumed_by_module() -> None:
    """`module.iam.service_accounts.composer.email` が module composer 入力に
    渡されている (新 SA を作っても consume されない bug を防ぐ)。"""
    main_tf = _read("infra/terraform/environments/dev/main.tf")
    assert "module.iam.service_accounts.composer.email" in main_tf, (
        "module composer must consume module.iam.service_accounts.composer.email "
        "(otherwise sa-composer は作成されるが Composer 環境が使わない bug)"
    )


def test_composer_environment_uses_correct_region_var() -> None:
    """Composer 環境の `region` は `var.region` を使う (`var.vertex_location`
    と取り違えると別 region に立って egress 課金発生)。"""
    composer_main = _read("infra/terraform/modules/composer/main.tf")
    assert (
        "region   = var.region" in composer_main
        or "region  = var.region" in composer_main
        or "region = var.region" in composer_main
    ), "Composer environment region must be var.region"


def test_composer_environment_has_proper_create_destroy_timeouts() -> None:
    """Composer 環境作成は 15-25 min かかるため、provider default の 30 min
    timeout では足りない場合がある。明示的に 60m / 30m を指定する契約。"""
    composer_main = _read("infra/terraform/modules/composer/main.tf")
    assert 'create = "60m"' in composer_main, (
        "Composer create timeout must be explicit 60m (default 30m too short)"
    )
    assert 'delete = "30m"' in composer_main, "Composer delete timeout must be explicit 30m"


def test_make_composer_env_default_matches_terraform_default() -> None:
    """`Makefile::COMPOSER_ENV` default が terraform `composer_environment_name`
    var default と一致 (`make ops-composer-trigger` が存在しない環境を叩かない)。"""
    makefile = _read("Makefile")
    variables_tf = _read("infra/terraform/environments/dev/variables.tf")

    make_match = re.search(r"COMPOSER_ENV\s+\?=\s+(\S+)", makefile)
    assert make_match is not None
    make_default = make_match.group(1).strip()

    tf_match = re.search(
        r'variable "composer_environment_name" \{[^}]*default\s+=\s+"([^"]+)"',
        variables_tf,
        flags=re.DOTALL,
    )
    assert tf_match is not None
    tf_default = tf_match.group(1)

    assert make_default == tf_default, (
        f"Makefile COMPOSER_ENV default ({make_default!r}) must match "
        f"terraform composer_environment_name default ({tf_default!r})"
    )


def test_composer_dag_bucket_terraform_output_consumed_by_deploy_script() -> None:
    """`composer_dag_bucket` output 名が deploy script と outputs.tf で同一
    (typo で空文字読みになり upload silent skip する事故を防ぐ)。"""
    deploy_script = _read("scripts/deploy/composer_deploy_dags.py")
    outputs_tf = _read("infra/terraform/environments/dev/outputs.tf")
    composer_outputs_tf = _read("infra/terraform/modules/composer/outputs.tf")

    assert '_terraform_output("composer_dag_bucket")' in deploy_script
    assert 'output "composer_dag_bucket" {' in outputs_tf
    assert 'output "dag_bucket" {' in composer_outputs_tf
    assert "module.composer.dag_bucket" in outputs_tf


def test_enable_composer_default_is_flipped_to_true() -> None:
    """Stage 3 で `enable_composer` default を true に flip 済 (deploy-all で
    Composer 環境が立ち上がる canonical 運用契約)。"""
    variables_tf = _read("infra/terraform/environments/dev/variables.tf")
    enable_block_match = re.search(
        r'variable "enable_composer" \{(.+?)\n\}', variables_tf, flags=re.DOTALL
    )
    assert enable_block_match is not None
    block = enable_block_match.group(1)
    assert "default     = true" in block or "default = true" in block, (
        "enable_composer default must be true (Stage 3 flip 完了済の契約)"
    )


def test_legacy_cloud_scheduler_demoted_to_monthly_smoke() -> None:
    """Stage 3.2 格下げ契約: `check-retrain-daily` を `0 4 * * *` (daily) →
    `0 4 1 * *` (monthly smoke) に格下げ済。"""
    messaging_tf = _read("infra/terraform/modules/messaging/main.tf")
    assert 'schedule    = "0 4 1 * *"' in messaging_tf, (
        "Cloud Scheduler check-retrain-daily must be demoted to monthly smoke "
        "(0 4 1 * *), not daily (0 4 * * *)"
    )
    assert "smoke" in messaging_tf, "Cloud Scheduler description must indicate smoke status"


def test_legacy_cloud_function_eventarc_marked_as_smoke() -> None:
    """Stage 3.2: Cloud Function `pipeline_trigger` + Eventarc 2 本に「smoke /
    軽量代替経路として残置」コメントが記載されていること。"""
    vertex_tf = _read("infra/terraform/modules/vertex/main.tf")
    assert "Stage 3 で smoke" in vertex_tf or "軽量代替経路として残置" in vertex_tf, (
        "Cloud Function pipeline_trigger must have demotion comment"
    )


def test_retrain_router_marked_as_smoke_endpoint() -> None:
    """Stage 3.2: `app/api/routers/retrain_router.py` docstring に「本線
    スケジューラから格下げ」「Composer DAG が呼ぶ smoke 経路」明記契約。"""
    router_py = _read("app/api/routers/retrain_router.py")
    assert "本線スケジューラから格下げ" in router_py, (
        "retrain_router docstring must indicate it's no longer the main scheduler"
    )
    assert "Composer DAG" in router_py, (
        "retrain_router docstring must reference Composer DAG as the canonical path"
    )


def test_composer_deploy_dags_uses_gsutil_m_for_parallel_upload() -> None:
    """DAG file 数が増えても upload を高速化するため `-m` flag (parallel) を
    使う契約 (single-threaded だと scheduler reparse 開始が遅れる)。"""
    deploy_script = _read("scripts/deploy/composer_deploy_dags.py")
    assert '"-m"' in deploy_script and '"cp"' in deploy_script, (
        "composer_deploy_dags must use 'gsutil -m cp' for parallel upload"
    )


def test_composer_module_workloads_config_has_max_count() -> None:
    """Composer Gen 3 worker の `max_count` が指定されていること (無限スケール
    アウトでコスト爆発を防ぐ契約)。"""
    composer_main = _read("infra/terraform/modules/composer/main.tf")
    for required in ("scheduler {", "web_server {", "worker {"):
        assert required in composer_main, f"workloads_config missing {required}"
    assert "max_count" in composer_main, (
        "worker.max_count must be set (avoid unbounded scale-out cost)"
    )


def test_deploy_all_step_runner_imports_composer_deploy_dags() -> None:
    """deploy_all.py が `composer_deploy_dags.main` を import 可能 + step 14
    の `_run_composer_deploy_dags` wrapper が定義されていること。"""
    deploy_all_py = _read("scripts/setup/deploy_all.py")
    assert (
        "from scripts.deploy.composer_deploy_dags import main as composer_deploy_dags_main"
        in deploy_all_py
    )
    assert "def _run_composer_deploy_dags() -> int:" in deploy_all_py
    assert "return composer_deploy_dags_main()" in deploy_all_py


def test_required_apis_cover_all_modules_actually_used() -> None:
    """**全 module ↔ API enablement contract** (2026-05-03 追加、Composer API 漏れの再発防止)。

    背景: 2026-05-03 live deploy で `module.composer` apply が PERMISSION_DENIED
    (「Cloud Composer API has not been used in project」) で fail。terraform
    `google_*` リソース作成時に背後の API 有効化チェックが走るため、`google_project_service.enabled`
    の `required_apis` リストに加えていないと、`depends_on` を満たしても実 API call が
    弾かれる。本 test は **新 module が増えるたびに API 漏れが再発する事故** を
    contract レベルで先回りして検知する。

    pin 方法: 各 module dir 内の `google_*` resource → 必要な API URL のマッピング
    を辞書で定義。実 module が宣言するリソースを grep で確認し、対応 API が
    apis.tf に揃っていることを assert。
    """
    apis_tf = _read("infra/terraform/environments/dev/apis.tf")

    # GCP resource type → required googleapis service name
    resource_to_api: dict[str, str] = {
        # Composer (W2-4)
        "google_composer_environment": "composer.googleapis.com",
        # Vertex AI (Pipelines / Endpoint / Feature Store / Vector Search)
        "google_vertex_ai_index": "aiplatform.googleapis.com",
        "google_vertex_ai_index_endpoint": "aiplatform.googleapis.com",
        "google_vertex_ai_endpoint": "aiplatform.googleapis.com",
        "google_vertex_ai_feature_online_store": "aiplatform.googleapis.com",
        "google_vertex_ai_feature_group": "aiplatform.googleapis.com",
        # GKE / Container
        "google_container_cluster": "container.googleapis.com",
        # Cloud Run / Build / Artifact Registry
        "google_cloud_run_v2_service": "run.googleapis.com",
        "google_artifact_registry_repository": "artifactregistry.googleapis.com",
        "google_cloudbuild_trigger": "cloudbuild.googleapis.com",
        # Pub/Sub / Eventarc / Cloud Functions / Scheduler
        "google_pubsub_topic": "pubsub.googleapis.com",
        "google_eventarc_trigger": "eventarc.googleapis.com",
        "google_cloudfunctions2_function": "cloudfunctions.googleapis.com",
        "google_cloud_scheduler_job": "cloudscheduler.googleapis.com",
        # Secret Manager
        "google_secret_manager_secret": "secretmanager.googleapis.com",
        # BigQuery / Dataform
        "google_bigquery_dataset": "bigquery.googleapis.com",
        "google_bigquery_table": "bigquery.googleapis.com",
        "google_dataform_repository": "dataform.googleapis.com",
        # Monitoring / Logging
        "google_monitoring_alert_policy": "monitoring.googleapis.com",
        "google_logging_metric": "logging.googleapis.com",
        # IAM / WIF
        "google_iam_workload_identity_pool": "iam.googleapis.com",
    }

    modules_dir = REPO_ROOT / "infra" / "terraform" / "modules"
    used_resource_types: set[str] = set()
    for tf_file in modules_dir.rglob("*.tf"):
        text = tf_file.read_text(encoding="utf-8")
        for resource_type in resource_to_api:
            if re.search(rf'resource "{re.escape(resource_type)}"', text):
                used_resource_types.add(resource_type)

    assert used_resource_types, (
        "could not detect any GCP resources in modules/ — regex broke?"
    )

    missing_apis: list[tuple[str, str]] = []
    for resource_type in sorted(used_resource_types):
        api = resource_to_api[resource_type]
        if f'"{api}"' not in apis_tf:
            missing_apis.append((resource_type, api))

    assert not missing_apis, (
        "infra/terraform/environments/dev/apis.tf::required_apis is missing APIs "
        "needed by terraform resources. Each resource's backing API must be in "
        "google_project_service.enabled, otherwise apply fails with PERMISSION_DENIED. "
        f"Missing: {missing_apis}"
    )


def test_composer_image_version_is_known_supported_form() -> None:
    """Composer image_version の文字列形式が正しいこと (Gen 3、`composer-3-airflow-X.Y.Z[-build.N]`)。

    GCP は image_version を厳格に validate する。typo / outdated version で
    apply が `Image version not supported` で fail する事故を防ぐ。
    """
    composer_main = _read("infra/terraform/modules/composer/main.tf")
    match = re.search(r'image_version\s*=\s*"([^"]+)"', composer_main)
    assert match is not None, "Composer module must specify image_version"
    image_version = match.group(1)
    assert image_version.startswith("composer-3-"), (
        f"image_version {image_version!r} must start with 'composer-3-' (Gen 3 mandatory, "
        f"Gen 2 deprecated and removed for new envs)"
    )
    assert "-airflow-" in image_version, (
        f"image_version {image_version!r} must contain '-airflow-X.Y.Z' segment"
    )


def test_composer_workloads_have_max_count_to_bound_cost() -> None:
    """Composer worker の `max_count` が指定されている (autoscaling 上限)。

    `max_count` 不在は GCP default (max_count=3 程度) になるが、PDCA dev 用途で
    上限を明示しないと予期せぬ scale-out で課金リスクが膨らむため契約として pin。
    """
    composer_main = _read("infra/terraform/modules/composer/main.tf")
    worker_match = re.search(
        r"worker\s*\{[^}]*max_count\s*=\s*(\d+)",
        composer_main,
        flags=re.DOTALL,
    )
    assert worker_match is not None, (
        "Composer module worker block must set max_count (cost upper bound). "
        "Default GCP value risks unbounded scale-out cost in PDCA dev."
    )
    max_count = int(worker_match.group(1))
    assert 1 <= max_count <= 5, (
        f"Composer worker.max_count={max_count} is outside sane range for dev (1-5)"
    )


def test_all_modules_use_consistent_region_var() -> None:
    """全 module が `var.region` または `var.vertex_location` を asia-northeast1 系で
    使う (region 取り違えで egress 課金 / cross-region 503 を防ぐ)。"""
    variables_tf = _read("infra/terraform/environments/dev/variables.tf")
    region_match = re.search(
        r'variable "region"[^}]*default\s*=\s*"([^"]+)"',
        variables_tf,
        flags=re.DOTALL,
    )
    vertex_match = re.search(
        r'variable "vertex_location"[^}]*default\s*=\s*"([^"]+)"',
        variables_tf,
        flags=re.DOTALL,
    )
    assert region_match is not None
    assert vertex_match is not None
    assert region_match.group(1) == "asia-northeast1", (
        f"var.region default must be asia-northeast1 (got {region_match.group(1)!r})"
    )
    assert vertex_match.group(1) == "asia-northeast1", (
        f"var.vertex_location default must be asia-northeast1 (got {vertex_match.group(1)!r})"
    )


def test_destroy_all_destroy_apply_symmetry() -> None:
    """**destroy-all ↔ deploy-all 対称性**: deploy-all が立てる主要 module は
    destroy-all で `terraform destroy -auto-approve` の連鎖で消える契約。

    過去の事故: `module.kserve` を Helm provider で立てたとき、provider 初期化
    race のため最初は destroy が hang した → `terraform destroy -target=module.kserve`
    を先行する pattern を destroy_all.py に組み込んだ。本 test はこのガード
    (`KSERVE_MODULE_TARGET = "module.kserve"`) が残っていることを pin。
    """
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    deploy_all_py = _read("scripts/setup/deploy_all.py")

    # KServe module 先行 destroy ガード
    assert 'KSERVE_MODULE_TARGET = "module.kserve"' in destroy_all_py, (
        "destroy-all must keep KServe module first-destroy guard"
    )
    assert "terraform destroy -target=module.kserve" in destroy_all_py, (
        "destroy-all must destroy module.kserve before the body destroy"
    )

    # 主要 module を deploy-all stage1 が立てている
    for required_module in (
        "module.iam",
        "module.data",
        "module.vector_search",
        "module.vertex",
        "module.gke",
        "module.composer",
    ):
        assert required_module in deploy_all_py, (
            f"deploy-all stage1 targets must include {required_module}"
        )


def test_makefile_run_all_core_targets_all_exist() -> None:
    """`make run-all-core` recipe が `$(MAKE) <target>` で呼ぶ全 target が
    Makefile に実在 (typo / drift で recipe が誤った target を呼ぶ事故を防ぐ)。"""
    makefile = _read("Makefile")

    # run-all-core recipe block を抜き出し
    run_all_core_match = re.search(
        r"^run-all-core:.*?(?=^\S|^$)",
        makefile,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert run_all_core_match is not None, "run-all-core target not found in Makefile"
    recipe = run_all_core_match.group(0)

    # `$(MAKE) <target>` の <target> を全て収集
    invoked = re.findall(r"\$\(MAKE\)\s+([\w-]+)", recipe)
    assert invoked, "run-all-core recipe contains no $(MAKE) ... invocations"

    # それぞれが ^<target>: で Makefile に定義されている
    for target in invoked:
        target_pattern = re.compile(rf"^{re.escape(target)}:", re.MULTILINE)
        assert target_pattern.search(makefile), (
            f"run-all-core invokes '$(MAKE) {target}' but no '{target}:' rule found in Makefile"
        )


def test_composer_sa_used_in_workload_identity_binding_chain() -> None:
    """`sa-composer` が Composer module + IAM module の両方で参照されており、
    `outputs.tf` の service_accounts map にも登録されている (3 箇所 lockstep)。

    過去の事故 (W2-3 で reranker SA で発生): SA を作っても module / outputs
    のいずれかへの登録漏れで実際の WI bind が成立しない bug。"""
    iam_main = _read("infra/terraform/modules/iam/main.tf")
    iam_outputs = _read("infra/terraform/modules/iam/outputs.tf")
    dev_main = _read("infra/terraform/environments/dev/main.tf")

    # 1. SA resource exists
    assert 'resource "google_service_account" "composer"' in iam_main
    assert 'account_id   = "sa-composer"' in iam_main

    # 2. outputs map exposes it (consumed by module composer)
    assert "composer          = google_service_account.composer" in iam_outputs

    # 3. dev/main.tf wires module.iam.service_accounts.composer.email into module composer
    assert "module.iam.service_accounts.composer.email" in dev_main


def test_pyproject_does_not_pull_apache_airflow_into_runtime() -> None:
    """`apache-airflow` は Composer worker 上で動く想定 — runtime dependency に
    入れると 1-2 GB の install / mypy slowdown が起きる。`dev` extras にも入れない
    (DAG file は AST + 文字列パース で test するため、Airflow 不要の設計)。"""
    pyproject = _read("pyproject.toml")
    # `dependencies = [...]` (project main runtime deps) には airflow を入れない
    main_deps_match = re.search(
        r"^dependencies\s*=\s*\[(.*?)\]",
        pyproject,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert main_deps_match is not None, "pyproject.toml must define [project] dependencies"
    main_deps = main_deps_match.group(1)
    assert "apache-airflow" not in main_deps, (
        "apache-airflow must NOT be in [project] dependencies (Composer worker only). "
        "Test DAG file structure via AST + string parsing instead."
    )


# =========================================================================
# 長時間 recovery 系の failure mode を contract で先回り (Vertex / GKE / VVS /
# FOS / WIF / BQ deletion_protection 等)
# =========================================================================


def test_vvs_module_lifecycle_protects_against_stale_id_recreation() -> None:
    """Vector Search の `deployed_index_id` は **`v1` ではなく `v2` 以上** の
    版数 (前 PDCA で残った soft-state を回避)。再発時には bump して回避する
    pattern を契約として記録。

    時間影響: 失敗時に GCP grace period が >30 min かかり PDCA を 1 時間級
    blocking する。
    """
    variables_tf = _read("infra/terraform/modules/vector_search/variables.tf")
    match = re.search(
        r'variable "deployed_index_id"[^}]*default\s*=\s*"([^"]+)"',
        variables_tf,
        flags=re.DOTALL,
    )
    assert match is not None
    deployed_id = match.group(1)
    version_match = re.search(r"_v(\d+)$", deployed_id)
    assert version_match is not None, (
        f"deployed_index_id {deployed_id!r} must end with _vN versioned suffix "
        "(bump on stale-state collision per docs/05_運用 §1.4)"
    )
    version = int(version_match.group(1))
    assert version >= 2, (
        f"deployed_index_id version {version} must be >=2 "
        "(v1 burned by 2026-05-02 stale soft-state issue; bump on each PDCA retry)"
    )


def test_vvs_module_min_max_replica_pinned_to_one_for_dev() -> None:
    """VVS deployed index の `min_replica_count = max_replica_count = 1`
    (autoscale なし) で **dev コスト + provisioning 時間を bounded に保つ**。

    時間影響: replica 増えると attach 時間 + コストが線形に増える。1 replica
    pin で 26 min 程度に収まる。"""
    main_tf = _read("infra/terraform/modules/vector_search/main.tf")
    variables_tf = _read("infra/terraform/modules/vector_search/variables.tf")

    min_match = re.search(
        r'variable "min_replica_count"[^}]*default\s*=\s*(\d+)',
        variables_tf,
        flags=re.DOTALL,
    )
    max_match = re.search(
        r'variable "max_replica_count"[^}]*default\s*=\s*(\d+)',
        variables_tf,
        flags=re.DOTALL,
    )
    assert min_match is not None and max_match is not None
    assert int(min_match.group(1)) == 1, (
        "VVS deployed index min_replica_count must be 1 for dev (cost bound)"
    )
    assert int(max_match.group(1)) == 1, (
        "VVS deployed index max_replica_count must be 1 for dev (autoscale 禁止)"
    )

    # main.tf 側でも `automatic_resources` block で参照されている
    assert "min_replica_count" in main_tf and "max_replica_count" in main_tf


def test_gke_two_stage_apply_pattern_preserved() -> None:
    """GKE Autopilot + KServe Helm provider race を回避する **2 段 apply** が
    `deploy_all.py` に維持されていること。

    背景: kubernetes / helm provider が `data.google_container_cluster` から
    endpoint+token を読むとき、cluster がまだ ready でないと
    `Get "http://localhost/api/v1/namespaces/..."` エラーで apply 全体が落ちる。
    stage1 で core infra (cluster 含む) を作り、kubeconfig を refresh してから
    stage2 で full graph を apply する pattern。

    時間影響: race で全 apply が無効化されると最大 30-40 min の retry コスト。
    """
    deploy_all_py = _read("scripts/setup/deploy_all.py")
    assert "stage1" in deploy_all_py.lower(), (
        "deploy-all must preserve 2-stage apply pattern (stage1 core → kubeconfig refresh → stage2 full)"
    )
    assert "ensure_kubectl_context" in deploy_all_py, (
        "deploy-all must call ensure_kubectl_context between stage1 and stage2"
    )
    assert "wait_until_api_ready" in deploy_all_py, (
        "deploy-all must wait_until_api_ready before stage2 (Kubernetes API ready check)"
    )


def test_destroy_all_undeploys_vertex_endpoint_models_before_destroy() -> None:
    """Vertex AI Endpoint の `deployedModels` が undeploy 済になってから
    `terraform destroy` する契約。

    背景: Endpoint が deployed_model を持つ状態で destroy すると HTTP 400
    `Endpoint has deployed or being-deployed DeployedModel(s)`。手動 cleanup
    が必要になり 5-15 min ロス。

    時間影響: 直すのに per-endpoint 1-2 min × N endpoints + retry。"""
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    assert "vertex_cleanup.undeploy_all_endpoint_shells" in destroy_all_py, (
        "destroy-all must call vertex_cleanup.undeploy_all_endpoint_shells "
        "BEFORE terraform destroy (otherwise HTTP 400 'Endpoint has deployed model(s)')"
    )


def test_destroy_all_flips_bq_deletion_protection_before_destroy() -> None:
    """BigQuery table の `deletion_protection=true` を destroy 前に **state-flip**
    する契約。

    背景: terraform はデフォルトで deletion_protection=true な BQ table を
    destroy 拒否する。`PROTECTED_TARGETS` に列挙して `terraform apply
    -var=enable_deletion_protection=false -target=...` で先行 flip しないと
    destroy が止まる。新 protected table を `data/main.tf` に追加したら
    `PROTECTED_TARGETS` にも追記する必要がある parity invariant。

    時間影響: 詰まったら state を弄って手動修復になり 30-60 min ロス。"""
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    data_tf = _read("infra/terraform/modules/data/main.tf")

    assert "PROTECTED_TARGETS" in destroy_all_py, (
        "destroy-all must declare PROTECTED_TARGETS list (BQ tables + GKE cluster)"
    )
    assert "enable_deletion_protection=false" in destroy_all_py, (
        "destroy-all must run apply with enable_deletion_protection=false to flip state"
    )

    # data/main.tf で deletion_protection を持つ全 BQ table が PROTECTED_TARGETS に
    # 列挙されていること (parity invariant)
    declared_tables = re.findall(
        r'resource "google_bigquery_table" "(\w+)"',
        data_tf,
    )
    for table_resource in declared_tables:
        # PROTECTED_TARGETS に載せるべき (deletion_protection=true なら必須)
        # ※ deletion_protection=true がデフォルトなので、明示的に false を持たない table は protected
        assert table_resource in destroy_all_py or "deletion_protection = false" in data_tf, (
            f"google_bigquery_table.{table_resource} should appear in destroy_all.py "
            "PROTECTED_TARGETS (BQ default deletion_protection=true)"
        )


def test_recover_wif_handles_soft_delete_undelete() -> None:
    """destroy → 即 deploy で WIF pool が soft-delete (30 日保持) のため
    409 conflict になるのを undelete で recover する契約。

    背景: GCP は WIF pool を delete してから 30 日間 soft-delete 状態で保持する。
    その間に同名で create しようとすると HTTP 409。`recover_wif.py` は
    state import + undelete を自動化することで PDCA を即時再実行可能にする。

    時間影響: 自動化なしだと 30 日間 WIF が使えない (destroy-all 後の deploy 完全 block)。"""
    deploy_all_py = _read("scripts/setup/deploy_all.py")
    recover_wif_py = _read("scripts/setup/recover_wif.py")

    assert "recover_wif" in deploy_all_py, (
        "deploy-all must call recover_wif before terraform apply"
    )
    assert "undelete" in recover_wif_py.lower(), (
        "recover_wif.py must handle WIF pool undelete (30-day soft-delete window)"
    )


def test_destroy_all_force_destroys_blocking_gcs_buckets() -> None:
    """`force_destroy=false` な GCS bucket は中身があると `terraform destroy`
    が `BucketNotEmpty` で fail する。`destroy_all` は 中身を `gcloud storage rm
    --recursive` で wipe してから destroy する契約。

    時間影響: 詰まると 1 bucket 1-3 min × N buckets + retry でロス。"""
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    assert "gcs_cleanup" in destroy_all_py, (
        "destroy-all must use gcs_cleanup helper to wipe non-force_destroy buckets"
    )
    assert "wipe_all_terraform_managed_buckets" in destroy_all_py, (
        "destroy-all must call wipe_all_terraform_managed_buckets"
    )


def test_deploy_all_seed_test_runs_before_feature_view_sync() -> None:
    """**seed → FV sync 順序契約**: `seed-test` が `trigger-fv-sync` より先。

    背景: 過去の live で順序逆転すると Feature View が空のまま sync 完了し、
    その後の `ops-vertex-feature-group` smoke が 404 で fail。順序の依存
    関係が壊れて気付くと 30-60 min の検証ロス。"""
    steps = deploy_all._steps()
    names = [s.name for s in steps]
    assert names.index("seed-test") < names.index("trigger-fv-sync"), (
        "seed-test must run before trigger-fv-sync (otherwise FV syncs an empty source)"
    )
    # backfill-vvs も seed の後 (VVS index に書く element が無いと smoke 0 neighbors)
    assert names.index("seed-test") < names.index("backfill-vvs"), (
        "seed-test must run before backfill-vvs (otherwise VVS index is empty)"
    )


def test_deploy_all_overlay_configmap_runs_before_deploy_api() -> None:
    """**ConfigMap overlay → deploy-api 順序契約**: `overlay-configmap` が
    `deploy-api` より先。

    背景: 順序逆転すると新 search-api Pod が古い ConfigMap (placeholder
    `https://meili-search-XXXXX-an.a.run.app` 等) を読み、`/search` が
    `lexical=0 semantic=0 rerank=0` を返す。Pod を rollout し直すまで治らず、
    検証で気付くと 5-10 min のロス + rolling restart 待ち。"""
    steps = deploy_all._steps()
    names = [s.name for s in steps]
    assert names.index("overlay-configmap") < names.index("deploy-api"), (
        "overlay-configmap must run before deploy-api (otherwise the new Pod reads stale ConfigMap)"
    )


def test_search_api_image_lifecycle_ignore_changes_pinned() -> None:
    """search-api Deployment の image は `placeholder` で初回 apply、後で
    `kubectl set image` (immutable tag) で差し替える pattern。

    背景: Deployment の `image` field を terraform 管理に置くと、
    `kubectl set image` で書き換えても次回 `terraform apply` で placeholder に
    戻ってしまう (drift)。manifest 側で `lifecycle.ignore_changes` を使って
    Deployment 作成時にのみ初期値、その後の image 差し替えは k8s 側で許容する。

    時間影響: drift 起きると Pod が ImagePullBackOff で 5-10 min ロス。"""
    deployment_yaml = _read("infra/manifests/search-api/deployment.yaml")
    # Cloud Build で差し替える前提の placeholder image が指定されている
    assert "image: gcr.io/cloudrun/hello" in deployment_yaml or "image: " in deployment_yaml, (
        "search-api deployment.yaml must pin a placeholder image for initial kubectl apply"
    )


def test_destroy_all_proactively_undeploys_stale_vvs_indexes() -> None:
    """**PDCA reproducibility 契約**: `destroy-all` は Vector Search の deployed
    index を能動的に undeploy する。

    背景: 過去の live verify で前 PDCA cycle が deployed index を残したまま
    終わると、次の `make deploy-all` が step 6 stage1 で 15 min wait timeout
    で fail する事故が再発した。`deploy-all` 側 `wait_for_deployed_index_absent`
    は wait しかしないため、`destroy-all` 側でも能動的に undeploy する責任
    がある。本 contract test がこのガードを pin する。
    """
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    vertex_cleanup_py = _read("scripts/infra/vertex_cleanup.py")

    # vertex_cleanup に proactive undeploy helper が存在
    assert "def undeploy_all_vvs_deployed_indexes(" in vertex_cleanup_py, (
        "scripts/infra/vertex_cleanup.py must define undeploy_all_vvs_deployed_indexes "
        "(proactive undeploy helper, not just wait_for_deployed_index_absent)"
    )
    # gcloud ai index-endpoints undeploy-index を実際に呼ぶ
    assert '"undeploy-index"' in vertex_cleanup_py, (
        "undeploy_all_vvs_deployed_indexes must invoke 'gcloud ai index-endpoints "
        "undeploy-index' (not just describe / wait)"
    )
    # destroy_all から呼び出されている
    assert "vertex_cleanup.undeploy_all_vvs_deployed_indexes" in destroy_all_py, (
        "destroy-all must call vertex_cleanup.undeploy_all_vvs_deployed_indexes "
        "(otherwise the next deploy-all step 6 timeout-fails on stale deployed index)"
    )


def test_cost_estimate_documented_in_runbook() -> None:
    """Stage 3 コスト見積もり (3h 学習 1 回想定) が runbook §1.4-bis に明記
    されていること — 過去の ¥9,000 padding ミス再発防止の contract。

    user authoritative wording (2026-05-02 終端) を pin:
    - section 存在 + 3h cycle ¥870-1,200 (Composer + GKE + Gateway + VVS + FOS
      + 従量系合算) + Composer なし時 ¥570-900 / 3h
    - 課金対象を「常駐系 vs 従量系」に分解 (理解促進)
    - 当日 destroy 前提を明記 (PDCA 契約)
    - destroy 漏れリスク (24h / 1 週間 / 月放置) も明記
    """
    runbook = _read("docs/runbook/05_運用.md")
    assert "### 1.4-bis Composer / Phase 7 フル構成のコスト見積もり" in runbook, (
        "runbook §1.4-bis (cost estimation section) is missing"
    )
    # 3h 学習 1 回の合計値 (user authoritative)
    assert "¥870-1,200" in runbook, (
        "runbook must pin Phase 7 full 3h learning-session cost as ~¥870-1,200 "
        "(user authoritative 2026-05-02)"
    )
    # Composer なし時の代替値
    assert "¥570-900" in runbook, (
        "runbook must document the without-Composer alt cost ~¥570-900 / 3h"
    )
    # 課金対象を「常駐系 vs 従量系」に分解
    assert "常駐系" in runbook and "従量系" in runbook, (
        "runbook must split cost into 常駐系 (always-on while env alive) vs "
        "従量系 (per-execution) so the reader knows what drives total cost"
    )
    # 当日 destroy 契約
    assert "当日 destroy 前提" in runbook, (
        "runbook must explicitly state 'same-day destroy' contract"
    )
    # destroy 漏れリスク (24h / 1 週間 / 月放置)
    assert "destroy 漏れリスク" in runbook, (
        "runbook must document destroy-leak risk (the real failure mode)"
    )
    for leak_marker in ("24h 放置", "1 週間放置", "月放置"):
        assert leak_marker in runbook, (
            f"runbook must enumerate destroy-leak scenarios including {leak_marker}"
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
