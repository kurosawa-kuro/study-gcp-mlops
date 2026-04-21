# Phase 3 現行から目標構成への完全マッピング

> 注記: 旧パスは移行元トレースのため記録している。現行の参照先は `app/`, `ml/data`, `ml/training`, `infra/run/jobs`, `tests/unit/ml`。

作成日: 2026-04-21

目的:
- Phase 3 (`study-hybrid-search-cloud`) を、学習用途として理解しやすい責務ベース構成へ移行するための対応表を固定する
- 実ディレクトリ移動、import 修正、テスト再配置、ドキュメント更新の基準を 1 ファイルにまとめる

前提:
- 目標構成は以下を基準とする

```text
root/
├─ app/
│  ├─ api/
│  ├─ services/
│  ├─ schemas/
│  └─ main.py
│
├─ ml/
│  ├─ data/
│  │  ├─ loaders/
│  │  ├─ preprocess/
│  │  ├─ feature_engineering/
│  │  └─ datasets/
│  │
│  ├─ training/
│  │  ├─ trainer.py
│  │  ├─ experiments/
│  │  └─ model_builder.py
│  │
│  ├─ evaluation/
│  │  ├─ metrics/
│  │  ├─ validators/
│  │  ├─ comparators/
│  │  └─ report/
│  │
│  ├─ registry/
│  │  ├─ model_registry.py
│  │  ├─ artifact_store.py
│  │  └─ metadata_store.py
│  │
│  ├─ serving/
│  │  ├─ predictor.py
│  │  ├─ batch_predictor.py
│  │  └─ response_builder.py
│  │
│  └─ common/
│     ├─ config/
│     ├─ logging/
│     └─ utils/
│
├─ pipeline/
│  ├─ data_job/
│  │  └─ main.py
│  ├─ training_job/
│  │  └─ main.py
│  ├─ evaluation_job/
│  │  └─ main.py
│  ├─ batch_serving_job/
│  │  └─ main.py
│  └─ workflow/
│     └─ orchestration.md
│
├─ infra/
│  ├─ terraform/
│  │  ├─ modules/
│  │  └─ environments/
│  └─ run/
│     ├─ jobs/
│     └─ services/
│
├─ docs/
│  ├─ architecture/
│  ├─ operations/
│  └─ decisions/
│
├─ scripts/
│  ├─ dev/
│  ├─ ci/
│  └─ local/
│
└─ tests/
   ├─ unit/
   ├─ integration/
   └─ e2e/
```

原則:
- `app/` は利用者接点だけ残す
- `common/` は top-level に置かず `ml/common/` へ吸収する
- `ml/embed`, `ml/train`, `ml/sync` のような実行形態ベース分割ではなく、`data / training / evaluation / registry / serving` の責務ベースに分解する
- `pipeline/` は orchestration と job entrypoint を置く
- `tests/` は `unit / integration / e2e` の目的で分類する

## 1. Top-Level 対応

| 現行 | 目標 | 方針 |
|---|---|---|
| `app/` | `app/` | 維持。内部を再配置 |
| `common/` | `ml/common/` | 吸収 |
| `ml/` | `ml/` + `pipeline/` | 分解して再配置 |
| `infra/` | `infra/terraform/` | Terraform 領域へ再配置 |
| `scripts/` | `scripts/dev` / `scripts/ci` / `scripts/local` | 再分類 |
| `tests/` | `tests/unit` / `tests/integration` / `tests/e2e` | 再分類 |
| `definitions/` | `infra/terraform/` または `docs/architecture/` | 用途に応じて吸収 |
| `monitoring/` | `ml/evaluation/validators` または `docs/operations` | 吸収 |
| `docs/` | `docs/architecture` / `docs/operations` / `docs/decisions` | 再分類 |
| `env/` | 維持または `infra/run/` 補助設定へ寄せる | 後続判断 |

## 2. app/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `app/src/app/entrypoints/api.py` | `app/api/main.py` |
| `app/src/app/services/ranking.py` | `app/services/ranking_service.py` |
| `app/src/app/services/retrain_policy.py` | `app/services/retrain_policy.py` |
| `app/src/app/services/model_store.py` | `ml/registry/model_registry.py` または `ml/serving/predictor.py` |
| `app/src/app/schemas/search.py` | `app/schemas/search.py` |
| `app/src/app/middleware/request_logging.py` | `app/api/middleware/request_logging.py` |
| `app/src/app/adapters/candidate_retriever.py` | `ml/data/loaders/bigquery_candidate_loader.py` |
| `app/src/app/adapters/lexical_search.py` | `ml/data/loaders/meili_loader.py` |
| `app/src/app/adapters/cache_store.py` | `ml/common/utils/cache.py` または `ml/serving/response_builder.py` 補助 |
| `app/src/app/adapters/model_store.py` | `ml/registry/model_registry.py` |
| `app/src/app/adapters/publisher.py` | `pipeline/training_job/main.py` 補助 |
| `app/src/app/adapters/retrain.py` | `pipeline/training_job/main.py` |
| `app/src/app/adapters/training_job.py` | `pipeline/training_job/main.py` |
| `app/src/app/ports/*` | 学習用途では責務近傍へ吸収 |
| `app/tests/*` | `tests/unit/app_*` または `tests/integration/api_*` |

## 3. common/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `common/src/common/config.py` | `ml/common/config/settings.py` |
| `common/src/common/logging/structured_logging.py` | `ml/common/logging/structured_logging.py` |
| `common/src/common/run_id.py` | `ml/common/utils/run_id.py` |
| `common/src/common/feature_engineering.py` | `ml/data/feature_engineering/ranker_features.py` |
| `common/src/common/embeddings/e5_encoder.py` | `ml/data/preprocess/e5_encoder.py` |
| `common/src/common/ranking/metrics.py` | `ml/evaluation/metrics/ranking_metrics.py` |
| `common/src/common/ranking/label_gain.py` | `ml/evaluation/comparators/label_gain.py` |
| `common/src/common/schema/feature_schema.py` | `ml/common/utils/feature_schema.py` |
| `common/src/common/storage/gcs_artifact_store.py` | `ml/registry/artifact_store.py` |
| `common/src/common/adapters/bigquery_embedding_store.py` | `ml/registry/metadata_store.py` または `ml/data/loaders/embedding_store.py` |
| `common/src/common/ports/embedding_store.py` | `ml/registry/` 直下へ吸収 |
| `common/tests/*` | `tests/unit/common_*` |

## 4. ml/embed/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `ml/data/job.py` | `pipeline/data_job/main.py` |
| `ml/data/preprocess/embedding_runner.py` | `ml/data/preprocess/embedding_runner.py` |
| `ml/data/datasets/embed_settings.py` | `ml/data/datasets/embed_settings.py` |
| `infra/run/jobs/embedding/Dockerfile` | `infra/run/jobs/embedding/Dockerfile` |
| `ml/embed/tests/test_runner.py` | `tests/unit/data_embedding_runner_test.py` |

## 5. ml/train/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `ml/training/job.py` | `pipeline/training_job/main.py` |
| `ml/training/trainer.py` | `ml/training/trainer.py` |
| `ml/evaluation/metrics/training_metrics.py` | `ml/evaluation/metrics/training_metrics.py` |
| `ml/training/experiments/settings.py` | `ml/training/model_builder.py` または `ml/training/experiments/settings.py` |
| `infra/run/jobs/training/Dockerfile` | `infra/run/jobs/training/Dockerfile` |
| `ml/train/tests/test_trainer.py` | `tests/unit/training_trainer_test.py` |
| `ml/train/tests/test_cli_run.py` | `tests/integration/training_job_test.py` |
| `ml/train/tests/test_bigquery_ranker_repository.py` | `tests/unit/registry_metadata_store_test.py` |

## 6. ml/sync/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `ml/data/loaders/meili_sync.py` | `pipeline/data_job/main.py` または `ml/data/loaders/meili_sync.py` |
| `ml/sync/tests/*` | `tests/integration/data_sync_test.py` |

## 7. infra/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `infra/modules/*` | `infra/terraform/modules/*` |
| `infra/main.tf`, `provider.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `backend.tf`, `apis.tf` | `infra/terraform/environments/main/*` または `infra/terraform/` 直下 |
| `infra/README.md` | `docs/operations/infra.md` |
| Cloud Run / Job 実行概念 | `infra/run/jobs/`, `infra/run/services/` |

## 8. scripts/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `scripts/checks/layers.py` | `scripts/ci/check_layers.py` |
| `scripts/config/sync_dataform.py` | `scripts/dev/sync_config.py` |
| `scripts/deploy/api_local.py` | `scripts/local/deploy_app.py` |
| `scripts/deploy/training_job_local.py` | `scripts/local/deploy_training_job.py` |
| `scripts/ops/livez_check.py` | `scripts/local/check_livez.py` |
| `scripts/ops/search_check.py` | `scripts/local/check_search.py` |
| `scripts/ops/ranking_check.py` | `scripts/local/check_ranking.py` |
| `scripts/ops/feedback_check.py` | `scripts/local/check_feedback.py` |
| `scripts/ops/check_retrain.py` | `scripts/local/check_retrain.py` |
| `scripts/ops/training_label_seed.py` | `scripts/dev/seed_training_labels.py` |
| `scripts/setup/*` | `scripts/dev/*` |
| `scripts/sql/*.sql` | `docs/operations/sql/` または `ml/evaluation/report/sql/` |
| `scripts/_common.py` | `scripts/dev/_common.py` |

## 9. tests/ 現行 → 目標

| 現行 | 目標 |
|---|---|
| `tests/arch/test_import_boundaries.py` | `tests/unit/architecture_import_test.py` |
| `tests/infra/test_terraform_module_structure.py` | `tests/integration/infra_structure_test.py` |
| `tests/infra/test_infra_ranker_tables.py` | `tests/integration/infra_ranker_tables_test.py` |
| `tests/infra/test_workflows_structure.py` | `tests/integration/workflow_structure_test.py` |
| `tests/parity/test_feature_parity_ranking.py` | `tests/e2e/feature_parity_ranking_test.py` |
| `tests/parity/test_feature_parity_sql_ranker.py` | `tests/e2e/feature_parity_sql_test.py` |
| `tests/parity/test_dataform_workflow_settings.py` | `tests/integration/dataform_settings_test.py` |

## 10. definitions / monitoring / docs / env 現行 → 目標

| 現行 | 目標 |
|---|---|
| `definitions/assertions`, `features`, `includes`, `monitoring`, `sources`, `staging` | `docs/architecture/dataform/` または `infra/terraform/modules/dataform/` |
| `monitoring/validate_feature_skew.sql` 相当 | `ml/evaluation/validators/feature_skew.sql` または `docs/operations/monitoring.md` |
| `docs/教育資料/*` | `docs/architecture/education/*` または `docs/decisions/education/*` |
| `README.md`, `CLAUDE.md` | `docs/architecture/overview.md`, `docs/decisions/dev_guide.md` へ内容分割 |
| `env/config`, `env/secret` | 維持、または `infra/run/config/` と `infra/run/secrets/` 相当へ整理 |

## 11. 目標構成への集約イメージ

- `app/` は利用者接点だけ残す
- `ml/data/` に `embed`, `sync`, feature engineering, loaders を集約
- `ml/training/` に trainer, settings, experiment 補助を集約
- `ml/evaluation/` に metrics, parity, validators, reports を集約
- `ml/registry/` に model store, artifact store, BigQuery run metadata を集約
- `ml/serving/` に predictor, response builder, online ranking 補助を集約
- `pipeline/` に `data_job`, `training_job`, 将来の `evaluation_job`, `batch_serving_job` を置く
- `infra/` は `terraform` と `run` に二分する
- `tests/` は `unit / integration / e2e` に再構成する

## 12. 次アクション

1. top-level ディレクトリ移動順の決定
2. `pyproject.toml` の workspace / pythonpath 再設計
3. import path の機械置換
4. tests 再分類
5. ドキュメント参照更新
