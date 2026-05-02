"""Phase 7 canonical orchestration DAG #2: retrain_orchestration.

**本 DAG が本線 retrain schedule** (= Cloud Scheduler `check-retrain-daily` /
Vertex `PipelineJobSchedule` を置き換える上下関係。詳細: docs/architecture/
01_仕様と設計.md §3 / §3.6)。

責務:
1. retrain 判定 (`scripts.ops.check_retrain` を `/jobs/check-retrain` 経由で叩く)
2. Vertex Pipeline submit (`pipeline.workflow.compile --target train --submit`
   = `make ops-train-now` と同一 invocation。BashOperator で subprocess 呼出し
   して KFP 2.16 module-level import 問題を回避する)
3. Pipeline SUCCEEDED 待機 (`scripts.ops.vertex.pipeline_wait`)
4. Reranker promote (`scripts.ops.promote` — `AUTO_PROMOTE=true` のときのみ)

schedule: `0 19 * * *` UTC = 04:00 JST (`daily_feature_refresh` の 3 時間後)。
"""

from __future__ import annotations

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import ShortCircuitOperator

from pipeline.dags._common import DEFAULT_DAG_ARGS, env, fixed_start_date


def _gate_auto_promote() -> bool:
    """`AUTO_PROMOTE=true` のときだけ promote_reranker を走らせる safety gate。"""
    return env("AUTO_PROMOTE", "false").lower() == "true"


# `pipeline.workflow.compile` を subprocess 経由で叩くことで KFP 2.16 の
# module-level `@dsl.pipeline` 互換 issue (TASKS_ROADMAP §4.8 W2-9) を回避する。
# `make ops-train-now` と同じ引数列を使う (= live で実証済の path)。
SUBMIT_TRAIN_PIPELINE_CMD = (
    "uv run python -m pipeline.workflow.compile "
    "--target train --output-dir dist/pipelines --submit "
    '--project-id "$PROJECT_ID" --location "$VERTEX_LOCATION" '
    '--pipeline-root "gs://$PIPELINE_ROOT_BUCKET/runs" '
    '--service-account "sa-pipeline@$PROJECT_ID.iam.gserviceaccount.com"'
)


with DAG(
    dag_id="retrain_orchestration",
    description="Phase 7 canonical 本線 retrain DAG: check_retrain → submit → wait → promote",
    default_args=DEFAULT_DAG_ARGS,
    schedule="0 19 * * *",
    start_date=fixed_start_date(),
    catchup=False,
    tags=["phase7", "canonical", "retrain"],
) as dag:
    check_retrain = BashOperator(
        task_id="check_retrain",
        bash_command="uv run python -m scripts.ops.check_retrain",
    )

    submit_train_pipeline = BashOperator(
        task_id="submit_train_pipeline",
        bash_command=SUBMIT_TRAIN_PIPELINE_CMD,
    )

    wait_train_succeeded = BashOperator(
        task_id="wait_train_succeeded",
        bash_command="uv run python -m scripts.ops.vertex.pipeline_wait",
    )

    gate_auto_promote = ShortCircuitOperator(
        task_id="gate_auto_promote",
        python_callable=_gate_auto_promote,
    )

    promote_reranker = BashOperator(
        task_id="promote_reranker",
        bash_command="APPLY=1 uv run python -m scripts.ops.promote",
    )

    (
        check_retrain
        >> submit_train_pipeline
        >> wait_train_succeeded
        >> gate_auto_promote
        >> promote_reranker
    )
