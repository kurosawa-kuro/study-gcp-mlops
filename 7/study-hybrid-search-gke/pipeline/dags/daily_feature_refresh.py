"""Phase 7 canonical orchestration DAG #1: daily_feature_refresh.

責務: 日次で feature 系のデータを refresh:
1. Dataform workflow 実行 (`feature_mart.property_features_daily` など再計算)
2. Vertex AI Feature View sync (Feature Online Store 更新)
3. (opt-in) Vertex Vector Search incremental backfill

schedule: `0 16 * * *` UTC = 01:00 JST。`retrain_orchestration` (04:00 JST)
の 3 時間前に feature を refresh しておくため、本 DAG が先行する。

各 task は **BashOperator** で `uv run python -m ...` を呼ぶ — Composer worker
で `pipeline.workflow.compile` 等の重い module を import するコストを避け、
かつ既存 `make` target と同じ呼び出しパスを使うことで CI/live のバッキング
パスを揃える設計。

詳細: docs/architecture/01_仕様と設計.md §3.5 (Phase 6 6A の DAG = 本 phase
で本実装) と docs/tasks/TASKS_ROADMAP.md §4.7。
"""

from __future__ import annotations

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import ShortCircuitOperator

from pipeline.dags._common import DEFAULT_DAG_ARGS, env, fixed_start_date


def _gate_daily_vvs_refresh() -> bool:
    """`ENABLE_DAILY_VVS_REFRESH=true` のときだけ後段を走らせる short-circuit。"""
    return env("ENABLE_DAILY_VVS_REFRESH", "false").lower() == "true"


with DAG(
    dag_id="daily_feature_refresh",
    description="Phase 7 canonical: Dataform run + Feature View sync + (opt) VVS incremental backfill",
    default_args=DEFAULT_DAG_ARGS,
    schedule="0 16 * * *",
    start_date=fixed_start_date(),
    catchup=False,
    tags=["phase7", "canonical", "feature"],
) as dag:
    dataform_run = BashOperator(
        task_id="dataform_run",
        bash_command=(
            "gcloud dataform repositories workflow-invocations create "
            "--repository=hybrid-search-cloud "
            '--location="$REGION" '
            "--workflow-config=daily"
        ),
    )

    trigger_fv_sync = BashOperator(
        task_id="trigger_fv_sync",
        bash_command="uv run python -m scripts.infra.feature_view_sync",
    )

    gate_vvs_refresh = ShortCircuitOperator(
        task_id="gate_vvs_refresh",
        python_callable=_gate_daily_vvs_refresh,
    )

    backfill_vvs_incremental = BashOperator(
        task_id="backfill_vvs_incremental",
        bash_command="uv run python -m scripts.setup.backfill_vector_search_index --apply",
    )

    dataform_run >> trigger_fv_sync >> gate_vvs_refresh >> backfill_vvs_incremental
