"""Generic GCP resource state recovery — import existing GCP resources into tfstate.

**背景** (2026-05-03 incident postmortem):
- `runbook §1.4-emergency` の「緊急 cleanup 後の tfstate orphan cleanup」で、
  state list 全件を `state rm` で消すレシピがあった
- これは GCP 側で **本当に消えた resources** のための clean-up だが、`gcloud delete --async`
  で Composer / GKE / Cloud Run しか消していない場合、IAM SA / BigQuery / Pub/Sub /
  Cloud Function / Eventarc / Cloud Run (Meilisearch) などは GCP に残置
- 全件 state rm 後に `make deploy-all` を走らせると、stage1 tf-apply で
  `Error: alreadyExists` で多数の resource create が fail
- 特に IAM SA は soft-delete 30 日 window があるため、gcloud delete → 即 terraform
  create がさらに fail する罠あり

**本 module の役割**:
1. GCP 側に存在する resources を type ごとに list
2. 名前から terraform address を逆引き (静的 mapping、`infra/terraform/modules/*/main.tf`
   と一致しているか contract test で固定)
3. state に既に entry があれば skip、無ければ `terraform import` で取り込む

idempotent: 何度叩いても余分な import は走らない。`vertex_import.py` の VVS 永続化
import と同じ pattern で、deploy_all.py が tf-apply 直前に呼ぶ。

**制限**:
- IAM bindings (`google_project_iam_member` etc.) は recover しない (依存 SA を import
  してから tf-apply で create_or_read される)
- GCS buckets は force_destroy 設計が module 側で固定されているため復元しない
- 教材用 dev project (`mlops-dev-a`) 専用。別 project への流用は mapping 拡張要
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Terraform address ↔ GCP resource mapping
# `infra/terraform/modules/*/main.tf` の resource declaration と一致させる。
# 不一致は `tests/integration/workflow/test_state_recovery_contract.py` で検出。
# ---------------------------------------------------------------------------

# IAM service accounts: account_id 'sa-X' → terraform address `module.iam.google_service_account.X`
# (X は dash-to-underscore 変換。例: sa-job-train → job_train)
IAM_SA_NAMES = (
    "api",
    "job_train",
    "job_embed",
    "dataform",
    "scheduler",
    "pipeline",
    "endpoint_encoder",
    "endpoint_reranker",
    "pipeline_trigger",
    "external_secrets",
    "github_deployer",
    "composer",
)

# BQ datasets (module.data)
BQ_DATASETS = ("mlops", "feature_mart", "predictions")

# BQ tables: (dataset, table_name, terraform_resource_name)
# table_name は GCP の table ID、terraform_resource_name は main.tf の resource label
BQ_TABLES = (
    ("mlops", "training_runs", "training_runs"),
    ("mlops", "search_logs", "search_logs"),
    ("mlops", "ranking_log", "ranking_log"),
    ("mlops", "feedback_events", "feedback_events"),
    ("mlops", "validation_results", "validation_results"),
    ("mlops", "model_monitoring_alerts", "model_monitoring_alerts"),
    ("mlops", "ranking_log_hourly_ctr", "ranking_log_hourly_ctr"),
    ("feature_mart", "property_features_daily", "property_features_daily"),
    ("feature_mart", "property_features_online_latest", "property_features_online_latest"),
    ("feature_mart", "property_embeddings", "property_embeddings"),
)

# Pub/Sub topics: (gcp_topic_name, module_name, terraform_resource_name)
PUBSUB_TOPICS = (
    ("ranking-log", "messaging", "ranking_log"),
    ("search-feedback", "messaging", "search_feedback"),
    ("retrain-trigger", "messaging", "retrain_trigger"),
    ("model-monitoring-alerts", "vertex", "model_monitoring_alerts"),
)

# Pub/Sub subscriptions: (gcp_sub_name, module_name, terraform_resource_name)
PUBSUB_SUBSCRIPTIONS = (
    ("ranking-log-to-bq", "messaging", "ranking_log_to_bq"),
    ("search-feedback-to-bq", "messaging", "search_feedback_to_bq"),
    ("monitoring-alerts-to-bq", "vertex", "monitoring_alerts_to_bq"),
)

# Cloud Function (Gen 2): (gcp_function_name, module_name, terraform_resource_name)
CLOUD_FUNCTIONS = (("pipeline-trigger", "vertex", "pipeline_trigger"),)

# Eventarc triggers: (gcp_trigger_name, module_name, terraform_resource_name)
EVENTARC_TRIGGERS = (
    ("retrain-to-pipeline", "vertex", "retrain_to_pipeline"),
    ("monitoring-to-pipeline", "vertex", "monitoring_to_pipeline"),
)

# Cloud Run services: (gcp_service_name, module_name, terraform_resource_name)
CLOUD_RUN_SERVICES = (("meili-search", "meilisearch", "meili_search"),)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _state_has(infra_dir: Path, addr: str) -> bool:
    """terraform state list <addr> が hit するか。"""
    proc = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "state", "list", addr],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and addr in (proc.stdout or "")


def _terraform_import(
    infra_dir: Path, addr: str, gcp_id: str, *, terraform_var_args: list[str]
) -> bool:
    print(f"==> terraform import {addr} ← {gcp_id}")
    proc = subprocess.run(
        [
            "terraform",
            f"-chdir={infra_dir}",
            "import",
            *terraform_var_args,
            addr,
            gcp_id,
        ],
        check=False,
    )
    return proc.returncode == 0


def _gcloud_json(args: list[str]) -> list[dict]:
    """gcloud `--format=json` の結果を list[dict] に。失敗時は []。"""
    proc = subprocess.run(args, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout) if (proc.stdout or "").strip() else []
        return payload if isinstance(payload, list) else []
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------
# IAM SA recovery
# ---------------------------------------------------------------------------


def _recover_iam_sas(infra_dir: Path, project_id: str, var_args: list[str]) -> int:
    imported = 0
    existing = _gcloud_json(
        ["gcloud", "iam", "service-accounts", "list", f"--project={project_id}", "--format=json"]
    )
    existing_emails = {sa.get("email", "") for sa in existing}
    for sa_name in IAM_SA_NAMES:
        addr = f"module.iam.google_service_account.{sa_name}"
        # account_id は dash 区切り (terraform `sa-{tf_name.replace("_","-")}`)
        # ただし terraform `account_id` field は main.tf 内で個別指定。確実な mapping は
        # email = sa-{tf_name.replace("_","-")}@<project>.iam.gserviceaccount.com
        gcp_account_id = "sa-" + sa_name.replace("_", "-")
        email = f"{gcp_account_id}@{project_id}.iam.gserviceaccount.com"
        if email not in existing_emails:
            continue
        if _state_has(infra_dir, addr):
            continue
        gcp_resource_name = f"projects/{project_id}/serviceAccounts/{email}"
        if _terraform_import(infra_dir, addr, gcp_resource_name, terraform_var_args=var_args):
            imported += 1
    return imported


# ---------------------------------------------------------------------------
# BigQuery dataset / table recovery
# ---------------------------------------------------------------------------


def _bq_exists(project_id: str, gcp_id: str) -> bool:
    """bq show GCP_ID returns 0 if exists."""
    proc = subprocess.run(
        ["bq", "show", "--project_id", project_id, "--format=none", gcp_id],
        check=False,
        capture_output=True,
    )
    return proc.returncode == 0


def _recover_bq(infra_dir: Path, project_id: str, var_args: list[str]) -> int:
    imported = 0
    for ds in BQ_DATASETS:
        addr = f"module.data.google_bigquery_dataset.{ds}"
        gcp_id = f"projects/{project_id}/datasets/{ds}"
        if not _bq_exists(project_id, f"{project_id}:{ds}"):
            continue
        if _state_has(infra_dir, addr):
            continue
        if _terraform_import(infra_dir, addr, gcp_id, terraform_var_args=var_args):
            imported += 1
    for ds, tbl, tf_name in BQ_TABLES:
        addr = f"module.data.google_bigquery_table.{tf_name}"
        gcp_id = f"projects/{project_id}/datasets/{ds}/tables/{tbl}"
        if not _bq_exists(project_id, f"{project_id}:{ds}.{tbl}"):
            continue
        if _state_has(infra_dir, addr):
            continue
        if _terraform_import(infra_dir, addr, gcp_id, terraform_var_args=var_args):
            imported += 1
    return imported


# ---------------------------------------------------------------------------
# Pub/Sub topic / subscription recovery
# ---------------------------------------------------------------------------


def _recover_pubsub(infra_dir: Path, project_id: str, var_args: list[str]) -> int:
    imported = 0
    existing_topics = {
        t.get("name", "").rsplit("/", 1)[-1]
        for t in _gcloud_json(
            ["gcloud", "pubsub", "topics", "list", f"--project={project_id}", "--format=json"]
        )
    }
    for gcp_name, module, tf_name in PUBSUB_TOPICS:
        addr = f"module.{module}.google_pubsub_topic.{tf_name}"
        if gcp_name not in existing_topics:
            continue
        if _state_has(infra_dir, addr):
            continue
        gcp_id = f"projects/{project_id}/topics/{gcp_name}"
        if _terraform_import(infra_dir, addr, gcp_id, terraform_var_args=var_args):
            imported += 1
    existing_subs = {
        s.get("name", "").rsplit("/", 1)[-1]
        for s in _gcloud_json(
            [
                "gcloud",
                "pubsub",
                "subscriptions",
                "list",
                f"--project={project_id}",
                "--format=json",
            ]
        )
    }
    for gcp_name, module, tf_name in PUBSUB_SUBSCRIPTIONS:
        addr = f"module.{module}.google_pubsub_subscription.{tf_name}"
        if gcp_name not in existing_subs:
            continue
        if _state_has(infra_dir, addr):
            continue
        gcp_id = f"projects/{project_id}/subscriptions/{gcp_name}"
        if _terraform_import(infra_dir, addr, gcp_id, terraform_var_args=var_args):
            imported += 1
    return imported


# ---------------------------------------------------------------------------
# Cloud Function / Eventarc / Cloud Run recovery
# ---------------------------------------------------------------------------


def _recover_cloudfunctions(
    infra_dir: Path, project_id: str, region: str, var_args: list[str]
) -> int:
    imported = 0
    existing = {
        f.get("name", "").rsplit("/", 1)[-1]
        for f in _gcloud_json(
            [
                "gcloud",
                "functions",
                "list",
                f"--project={project_id}",
                f"--regions={region}",
                "--format=json",
            ]
        )
    }
    for gcp_name, module, tf_name in CLOUD_FUNCTIONS:
        addr = f"module.{module}.google_cloudfunctions2_function.{tf_name}"
        if gcp_name not in existing:
            continue
        if _state_has(infra_dir, addr):
            continue
        gcp_id = f"projects/{project_id}/locations/{region}/functions/{gcp_name}"
        if _terraform_import(infra_dir, addr, gcp_id, terraform_var_args=var_args):
            imported += 1
    return imported


def _recover_eventarc(infra_dir: Path, project_id: str, region: str, var_args: list[str]) -> int:
    imported = 0
    existing = {
        t.get("name", "").rsplit("/", 1)[-1]
        for t in _gcloud_json(
            [
                "gcloud",
                "eventarc",
                "triggers",
                "list",
                f"--project={project_id}",
                f"--location={region}",
                "--format=json",
            ]
        )
    }
    for gcp_name, module, tf_name in EVENTARC_TRIGGERS:
        addr = f"module.{module}.google_eventarc_trigger.{tf_name}"
        if gcp_name not in existing:
            continue
        if _state_has(infra_dir, addr):
            continue
        gcp_id = f"projects/{project_id}/locations/{region}/triggers/{gcp_name}"
        if _terraform_import(infra_dir, addr, gcp_id, terraform_var_args=var_args):
            imported += 1
    return imported


def _recover_cloud_run(infra_dir: Path, project_id: str, region: str, var_args: list[str]) -> int:
    imported = 0
    existing = {
        s.get("metadata", {}).get("name", "")
        for s in _gcloud_json(
            [
                "gcloud",
                "run",
                "services",
                "list",
                f"--project={project_id}",
                f"--region={region}",
                "--format=json",
            ]
        )
    }
    for gcp_name, module, tf_name in CLOUD_RUN_SERVICES:
        addr = f"module.{module}.google_cloud_run_v2_service.{tf_name}"
        if gcp_name not in existing:
            continue
        if _state_has(infra_dir, addr):
            continue
        gcp_id = f"projects/{project_id}/locations/{region}/services/{gcp_name}"
        if _terraform_import(infra_dir, addr, gcp_id, terraform_var_args=var_args):
            imported += 1
    return imported


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------


def recover_orphan_gcp_resources(
    infra_dir: Path,
    project_id: str,
    region: str,
    *,
    terraform_var_args: list[str] | None = None,
) -> int:
    """Discover existing GCP resources and import missing ones into tfstate.

    Returns the total number of resources imported.
    """
    var_args = list(terraform_var_args or [])
    print(f"==> state recovery: project={project_id} region={region}")
    total = 0
    total += _recover_iam_sas(infra_dir, project_id, var_args)
    total += _recover_bq(infra_dir, project_id, var_args)
    total += _recover_pubsub(infra_dir, project_id, var_args)
    total += _recover_cloudfunctions(infra_dir, project_id, region, var_args)
    total += _recover_eventarc(infra_dir, project_id, region, var_args)
    total += _recover_cloud_run(infra_dir, project_id, region, var_args)
    if total:
        print(f"==> state recovery: {total} orphan GCP resource(s) imported into state")
    else:
        print("==> state recovery: no orphan resources found")
    return total


def main(argv: list[str] | None = None) -> int:
    """CLI: invoke recovery directly (used by `make state-recover` smoke)."""
    import os

    project_id = os.environ.get("PROJECT_ID", "mlops-dev-a")
    region = (
        os.environ.get("VERTEX_LOCATION") or os.environ.get("REGION") or "asia-northeast1"
    )
    infra_dir = (
        Path(__file__).resolve().parents[2]
        / "infra"
        / "terraform"
        / "environments"
        / "dev"
    )
    var_args: list[str] = []
    github_repo = os.environ.get("GITHUB_REPO", "").strip()
    if github_repo:
        var_args.extend(["-var", f"github_repo={github_repo}"])
    oncall = os.environ.get("ONCALL_EMAIL", "").strip()
    if oncall:
        var_args.extend(["-var", f"oncall_email={oncall}"])
    recover_orphan_gcp_resources(infra_dir, project_id, region, terraform_var_args=var_args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
