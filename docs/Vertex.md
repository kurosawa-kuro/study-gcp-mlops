# Vertex AI 導入設計書

最終更新: 2026-03-26

---

## 1. 方針

- 既存構成（Cloud Run Job/Service, BigQuery, GCS, MLflow）はそのまま維持
- Vertex Pipelines (KFP v2) をオーケストレーション層として追加
- Vertex Training / Vertex Endpoints には移行しない

---

## 2. アーキテクチャ

### Before

```
Cloud Scheduler (毎日9:00 JST)
  → Cloud Run Job (ml-batch)
      → GCS (models/) + BigQuery (metrics) + GCS (logs/)

Cloud Run Service (ml-api)
  → BigQuery (RMSE最小モデル選択) → GCS (モデルロード) → POST /predict
```

### After

```
Vertex Pipeline Schedule (毎日9:00 JST)
  → Vertex Pipeline
      └── train_step (既存 ml-batch コンテナ再利用)
            → GCS (models/) + BigQuery (metrics) + GCS (logs/)

Cloud Run Service (ml-api) ← 変更なし
  → BigQuery → GCS → POST /predict
```

---

## 3. フェーズ分割

### Phase 9a - 最小構成（Vertex Pipelines）

1. `aiplatform.googleapis.com` API有効化
2. パイプラインアーティファクト用GCSバケット作成（`mlops-dev-a-vertex-pipeline`）
3. IAM追加（`roles/aiplatform.user` を compute SA に付与）
4. KFP v2で単一ステップパイプライン定義（既存ml-batchイメージを `container_component` で実行）
5. コンパイル → 手動サブミット → Vertex AI Console で確認
6. Cloud Schedulerは並行稼働のまま

### Phase 9b - パイプライン拡張

1. パイプラインを複数ステップに分割（train → evaluate → register）
2. KFPアーティファクト受け渡し（model_path, metrics）
3. 条件分岐（RMSEが改善した場合のみモデル登録）
4. Vertex Pipeline ScheduleでCloud Schedulerを置換（Terraform `paused = true`）

### Phase 9c - Vertex機能探索（任意）

1. Vertex Model Registry にモデル登録（GCS保存と併用）
2. Vertex Metadata で系譜追跡

---

## 4. Vertex機能の採用判断

| Vertex機能 | 判断 | 理由 |
|-----------|------|------|
| Vertex Pipelines (KFP) | 採用 | オーケストレーション可視化。本命 |
| Vertex Model Registry | 軽く採用(9c) | GCS保存と併用。カタログとして活用 |
| Vertex Experiments | 不採用 | MLflow維持。ベンダー中立性を重視 |
| Vertex Endpoints | 不採用 | Cloud Run Serviceで十分。コスト高 |
| Vertex Metadata | 自動取得のみ | KFPアーティファクト型指定で自動記録される |

---

## 5. 新規ファイル構成

```
src/pipeline/
  pipeline.py           # @dsl.pipeline 定義
  components.py         # @dsl.container_component 定義
  compile_pipeline.py   # YAML コンパイルスクリプト
  submit_pipeline.py    # Vertex AI へサブミット
  requirements.txt      # kfp>=2.7.0, google-cloud-aiplatform>=1.50.0
  requirements-dev.txt  # pytest
  test_pipeline.py      # コンパイルテスト
  compiled/             # コンパイル済みYAML出力先

makefiles/vertex.mk    # vertex-compile, vertex-run, vertex-list ターゲット
terraform/vertex.tf    # API有効化, パイプラインバケット, IAM
.github/workflows/vertex-pipeline.yml  # CI/CD
```

---

## 6. 既存ファイルへの変更

| ファイル | 変更内容 |
|---------|---------|
| `Makefile` | `include makefiles/vertex.mk` 追加 |
| `makefiles/gcp.mk` | `aiplatform.googleapis.com` API追加 |
| `terraform/variables.tf` | `pipeline_bucket_name` 変数追加 |
| `terraform/iam.tf` | `roles/aiplatform.user` + パイプラインバケットIAM追加 |
| `terraform/cloud_scheduler.tf` | Phase 9bで `paused = true` |
| `CLAUDE.md` | アーキテクチャ図・Tech Stack更新 |
| `docs/仕様、設計書.md` | Vertex セクション追加、ロードマップ更新 |

---

## 7. Terraform追加リソース

`terraform/vertex.tf` に以下を定義:

| リソース | 用途 |
|---------|------|
| `google_project_service.aiplatform` | aiplatform API有効化 |
| `google_storage_bucket.vertex_pipeline` | パイプラインアーティファクト格納 (`mlops-dev-a-vertex-pipeline`) |
| `google_project_iam_member.vertex_user` | compute SAに `roles/aiplatform.user` |
| `google_storage_bucket_iam_member.vertex_pipeline_writer` | compute SAにパイプラインバケット `roles/storage.objectAdmin` |

---

## 8. パイプライン実装概要（Phase 9a）

- `container_component` で既存 `ml-batch:latest` イメージをそのまま実行
- 環境変数は Cloud Run Job と同じ（GCS_BUCKET, JOB_NAME, BQ_DATASET）
- `submit_pipeline.py` で `aiplatform.PipelineJob` を使いサブミット
- `pipeline_root` = `gs://mlops-dev-a-vertex-pipeline/runs`

### パイプライン定義イメージ

```python
from kfp import dsl

@dsl.container_component
def ml_batch_train():
    return dsl.ContainerSpec(
        image="asia-northeast1-docker.pkg.dev/mlops-dev-a/mlops-dev-a-docker/ml-batch:latest",
        command=["python", "main.py"],
    )

@dsl.pipeline(
    name="california-housing-training",
    description="California Housing ML学習パイプライン"
)
def ml_pipeline():
    ml_batch_train()
```

### サブミットイメージ

```python
from google.cloud import aiplatform

aiplatform.init(
    project="mlops-dev-a",
    location="asia-northeast1",
    staging_bucket="gs://mlops-dev-a-vertex-pipeline",
)

job = aiplatform.PipelineJob(
    display_name="ml-training-run",
    template_path="compiled/pipeline.yaml",
    pipeline_root="gs://mlops-dev-a-vertex-pipeline/runs",
)
job.run(service_account="{PROJECT_NUMBER}-compute@developer.gserviceaccount.com")
```

---

## 9. Makefileターゲット

`makefiles/vertex.mk`:

| ターゲット | 内容 |
|-----------|------|
| `vertex-compile` | パイプラインYAMLコンパイル |
| `vertex-run` | パイプライン実行（Vertex AI） |
| `vertex-list` | パイプライン実行履歴表示 |
| `vertex-test` | パイプラインテスト |

---

## 10. CI/CD

`.github/workflows/vertex-pipeline.yml`:

- トリガー: `main` push (`src/pipeline/**` 変更時) + 手動
- ジョブ1: コンパイル（YAML生成）
- ジョブ2: サブミット（Vertex AI へ送信）
- 既存の `batch-deploy.yml`, `api-deploy.yml` は変更なし

---

## 11. 検証方法

1. `make vertex-compile` でYAMLが生成されること
2. `make vertex-run` でVertex Pipelineが実行されること
3. GCP Console > Vertex AI > Pipelines で実行履歴が確認できること
4. GCS `models/` に新モデルが保存され、BigQuery `metrics` に行が追加されること
5. 既存の `make batch-run`（Cloud Run Job直接実行）も引き続き動作すること

---

## 12. コスト

| 項目 | 見込み |
|------|--------|
| Vertex Pipelines | 約$0.03/実行（単純パイプライン） |
| パイプラインGCSバケット | 最小限のストレージ費用 |
| Vertex Endpoints | 使用しない（$0） |
| Vertex Training | 使用しない（$0） |
