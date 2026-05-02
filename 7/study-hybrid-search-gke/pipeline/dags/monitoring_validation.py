"""Phase 7 canonical orchestration DAG #3: monitoring_validation.

責務: 日次で feature skew / model output drift / SLO + burn-rate を確認:
1. `validate_feature_skew.sql` を BigQuery で実行 → `mlops.validation_results`
2. `validate_model_output_drift.sql` を BigQuery で実行 → `mlops.model_monitoring_alerts`
3. SLO + burn-rate alert 確認 (`scripts.ops.slo_status`)

schedule: `30 19 * * *` UTC = 04:30 JST (`retrain_orchestration` の 30 分後)。

詳細: docs/architecture/01_仕様と設計.md §3 / §3.5 (Phase 6 6B PMLE 増設)。
"""

from __future__ import annotations

from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from pipeline.dags._common import DEFAULT_DAG_ARGS, fixed_start_date

REPO_ROOT = Path(__file__).resolve().parents[2]
SKEW_SQL_PATH = REPO_ROOT / "infra" / "sql" / "monitoring" / "validate_feature_skew.sql"
DRIFT_SQL_PATH = REPO_ROOT / "infra" / "sql" / "monitoring" / "validate_model_output_drift.sql"


with DAG(
    dag_id="monitoring_validation",
    description="Phase 7 canonical: feature skew + model output drift + SLO burn-rate",
    default_args=DEFAULT_DAG_ARGS,
    schedule="30 19 * * *",
    start_date=fixed_start_date(),
    catchup=False,
    tags=["phase7", "canonical", "monitoring"],
) as dag:
    run_feature_skew = BigQueryInsertJobOperator(
        task_id="run_feature_skew",
        configuration={
            "query": {
                "query": SKEW_SQL_PATH.read_text(encoding="utf-8"),
                "useLegacySql": False,
            },
        },
    )

    run_model_output_drift = BigQueryInsertJobOperator(
        task_id="run_model_output_drift",
        configuration={
            "query": {
                "query": DRIFT_SQL_PATH.read_text(encoding="utf-8"),
                "useLegacySql": False,
            },
        },
    )

    check_slo_burn_rate = BashOperator(
        task_id="check_slo_burn_rate",
        bash_command="uv run python -m scripts.ops.slo_status",
    )

    [run_feature_skew, run_model_output_drift] >> check_slo_burn_rate
