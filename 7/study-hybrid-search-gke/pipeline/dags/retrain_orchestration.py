"""Phase 7 canonical orchestration DAG #2: retrain_orchestration.

**本 DAG が本線 retrain schedule** (= Cloud Scheduler `check-retrain-daily` /
Vertex `PipelineJobSchedule` を置き換える上下関係。詳細: docs/architecture/
01_仕様と設計.md §3 / §3.6)。

責務:
1. retrain 判定 (`scripts.ops.check_retrain`)
2. Vertex Pipeline submit (`pipeline.workflow.compile --target train --submit`
   = `make ops-train-now` と同一 invocation。subprocess 呼出しで KFP 2.16
   module-level import 問題を回避する)
3. Pipeline SUCCEEDED 待機 (`scripts.ops.vertex.pipeline_wait`)
4. Reranker promote (`scripts.ops.promote` — `AUTO_PROMOTE=true` のときのみ)

schedule: `0 19 * * *` UTC = 04:00 JST (`daily_feature_refresh` の 3 時間後)。

**V5 fix (2026-05-03)**: 旧版は BashOperator + subprocess (Composer worker 上で
直接 `python -m ...` 実行) だったが、Composer worker に必要 venv が無く task
SUCCEEDED 未達 (canonical 違反)。新版は `KubernetesPodOperator` +
`composer-runner` image で実行 (= V5 = §4.1)。
"""

from __future__ import annotations

from airflow import DAG
from airflow.operators.python import ShortCircuitOperator

from pipeline.dags._common import DEFAULT_DAG_ARGS, env, fixed_start_date
from pipeline.dags._pod import python_pod


def _gate_auto_promote() -> bool:
    """`AUTO_PROMOTE=true` のときだけ promote_reranker を走らせる safety gate。"""
    return env("AUTO_PROMOTE", "false").lower() == "true"


# `pipeline.workflow.compile` を subprocess 経由で叩くことで KFP 2.16 の
# module-level `@dsl.pipeline` 互換 issue (TASKS_ROADMAP §4.8 W2-9) を回避する。
# `make ops-train-now` と同じ引数列を使う (= live で実証済の path)。
SUBMIT_TRAIN_PIPELINE_ARGS = [
    "--target",
    "train",
    "--output-dir",
    "dist/pipelines",
    "--submit",
    "--project-id",
    "$(GCP_PROJECT)",
    "--location",
    "$(VERTEX_LOCATION)",
    "--pipeline-root",
    "gs://$(PIPELINE_ROOT_BUCKET)/runs",
    "--service-account",
    "sa-pipeline@$(GCP_PROJECT).iam.gserviceaccount.com",
]


with DAG(
    dag_id="retrain_orchestration",
    description="Phase 7 canonical 本線 retrain DAG: check_retrain → submit → wait → promote",
    default_args=DEFAULT_DAG_ARGS,
    schedule="0 19 * * *",
    start_date=fixed_start_date(),
    catchup=False,
    tags=["phase7", "canonical", "retrain"],
) as dag:
    check_retrain = python_pod(
        task_id="check_retrain",
        module="scripts.ops.check_retrain",
    )

    # python -m pipeline.workflow.compile --target train --submit ...
    # (KFP 2.16 issue 回避のため subprocess 化、make ops-train-now と同一)
    submit_train_pipeline = python_pod(
        task_id="submit_train_pipeline",
        module="pipeline.workflow.compile",
        extra_args=SUBMIT_TRAIN_PIPELINE_ARGS,
    )

    wait_train_succeeded = python_pod(
        task_id="wait_train_succeeded",
        module="scripts.ops.vertex.pipeline_wait",
    )

    gate_auto_promote = ShortCircuitOperator(
        task_id="gate_auto_promote",
        python_callable=_gate_auto_promote,
    )

    promote_reranker = python_pod(
        task_id="promote_reranker",
        module="scripts.ops.promote",
        extra_env={"APPLY": "1"},
    )

    (
        check_retrain
        >> submit_train_pipeline
        >> wait_train_succeeded
        >> gate_auto_promote
        >> promote_reranker
    )
