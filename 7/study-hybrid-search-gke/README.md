# study-hybrid-search-gke

**不動産ハイブリッド検索 × LightGBM LambdaRank** を GKE + KServe で serving する MLOps 学習リポジトリ。Phase 5 (Vertex AI プリミティブ) を継承しつつ、**serving 層のみを GKE / KServe に差し替える** 最小差分版。

> **スコープ**: 不動産検索 (クエリ文 + フィルタ → ランキング上位 20 件) のみ。
> **Phase 5 からの差分**: `search-api` (Cloud Run → GKE Deployment + Gateway) / encoder / reranker (Vertex Endpoint → KServe `InferenceService`)。Pipelines / Feature Group / Model Registry / BigQuery VECTOR_SEARCH / Meilisearch は据え置き。

本 README は「機能の簡易説明 + 各ドキュメントへのリンク」だけを扱う (`docs/README.md` §1 の規約に従う)。環境構築・運用・実装詳細は下記 **§ ドキュメント** の各ファイルへ。

## アーキテクチャ

```
raw.properties (upstream ETL)
  └─ Dataform ─> feature_mart.properties_cleaned
                 feature_mart.property_features_daily (ctr / fav_rate / inquiry_rate)
  └─ Vertex AI KFP `property-search-embed` pipeline ─> feature_mart.property_embeddings
  └─ Vertex AI KFP `property-search-train` pipeline ─> GCS + mlops.training_runs + Vertex Model Registry

         └─ GKE Deployment `search-api` (FastAPI, in namespace `search`)
              ├─ /search   KServe encoder + Meilisearch (BM25) + BQ VECTOR_SEARCH → RRF → KServe reranker
              │             └─ Pub/Sub "ranking-log"    ─> BQ Subscription ─> mlops.ranking_log
              ├─ /feedback └─ Pub/Sub "search-feedback" ─> BQ Subscription ─> mlops.feedback_events
              └─ /jobs/check-retrain (Cloud Scheduler 04:00 JST → Gateway HTTPS endpoint)

         └─ KServe InferenceService `property-encoder` / `property-reranker` (namespace `kserve-inference`)
              ├─ property-encoder  multilingual-e5 Python predictor (storageUri = Model Registry artifact)
              └─ property-reranker MLServer LightGBM runtime     (storageUri = Model Registry artifact)

  └─ Cloud Run Service `meili-search` (GCS FUSE `/meili_data` mount、Phase 5 から据え置き)
  └─ Scheduled Query 05:00 JST `property_feature_skew_check` ─> mlops.validation_results
```

## ディレクトリ

| パス | 役割 |
|---|---|
| `infra/terraform/` | Terraform — BQ / GCS / Pub/Sub / GKE Autopilot / KServe Helm / Vertex Pipelines / Scheduler / WIF |
| `infra/manifests/` | K8s manifests (search-api Deployment + KServe InferenceService + Gateway + NetworkPolicy + PodMonitoring) |
| `definitions/` | Dataform — `properties_cleaned` + `property_features_daily` + assertions |
| `ml/common/` | 共有コード — `BigQueryEmbeddingStore` / `build_ranker_features` / ranking metrics / logging / gcs |
| `app/` | FastAPI search-api (`/search` / `/feedback` / `/jobs/check-retrain` — GKE Pod entrypoint) |
| `ml/data/` | 埋め込み/ローダー系の実装 |
| `ml/training/` | LambdaRank 学習本体 |
| `ml/serving/` | 推論補助ロジック |
| `pipeline/` | KFP エントリポイント (`data_job`, `training_job`, `evaluation_job`, `batch_serving_job`) |
| `scripts/local/` | deploy/setup/ops の運用コマンド群 (`deploy/api_gke.py` / `deploy/kserve_models.py` 追加) |
| `monitoring/` | feature skew Scheduled Query SQL |
| `.github/workflows/` | CI (ruff/mypy/pytest) + Terraform + deploy-api (kubectl set image) + deploy-*-image / deploy-pipeline / deploy-dataform |
| `docs/` | 仕様と設計・移行ロードマップ・実装カタログ・運用 (+ ドキュメント運用ルール) |

ファイル単位の一言コメントは [`docs/03_実装カタログ.md §2`](docs/03_実装カタログ.md)。

## 設計ハイライト

詳細は [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) と [`docs/01_仕様と設計.md`](docs/01_仕様と設計.md)。

- **Phase 5 からの差分**: serving 層のみ GKE + KServe に移行。Pipelines / Feature Group / Model Registry / BigQuery VECTOR_SEARCH / Meilisearch は **差分ゼロで維持**
- **Port / Adapter 設計**: `app.services.protocols` の `EncoderClient` / `RerankerClient` 実装を `VertexEndpointEncoder/Reranker` → `KServeEncoder/Reranker` に差し替えただけ (core / services / ports は無変更)
- **認可境界**: Gateway API + IAP + NetworkPolicy で Cloud Run の `--no-allow-unauthenticated` + IAM 相当を再現
- **Workload Identity**: Phase 5 の 9 SA をそのまま GKE KSA にバインドして使い回す (新規 SA は追加しない)
- **予測分布 drift 検知は縮退**: Vertex Model Monitoring v2 は Vertex Endpoint 前提なので Phase 6 では失う (復活方針は Phase 7+ で判断)
- **固定値**: プロジェクト `mlops-dev-a` / リージョン `asia-northeast1` / Python 3.12 / uv / Terraform 1.9

## デプロイ

`main` へのマージで path filter に応じて以下が走る:

| 変更 | 反応するワークフロー | 動作 |
|---|---|---|
| `infra/terraform/**` | `terraform.yml` | plan (PR コメント) → push で apply |
| `app/**`, `ml/**`, `infra/manifests/**` | `deploy-api.yml` | Docker build → Artifact Registry → `kubectl set image deployment/search-api` |
| `pipeline/data_job/**`, `ml/data/**` | `deploy-encoder-image.yml` | Docker build → push encoder image (Vertex Pipelines で使用) |
| `pipeline/training_job/**`, `ml/training/**` | `deploy-trainer-image.yml` | Docker build → push KFP trainer image |
| `ml/serving/**` | `deploy-reranker-image.yml` | Docker build → push reranker image |
| `pipeline/**`, `scripts/local/setup/**` | `deploy-pipeline.yml` | KFP templates compile → upload to GCS + Schedule setup |
| `definitions/**` | `deploy-dataform.yml` | `dataform compile` + Dataform API へ compilationResults POST |

認証はすべて WIF。

## ドキュメント

初めてこのリポジトリに触る人は、まず [`docs/04_運用.md §1 環境構築`](docs/04_運用.md) を上から叩く。

| ドキュメント | 目的 | 主な読者 |
|---|---|---|
| [`docs/README.md`](docs/README.md) | ドキュメント運用ルール (役割 / 権威順位 / 更新規約 / 書き方) | 文書を触る人全員 |
| [`docs/01_仕様と設計.md`](docs/01_仕様と設計.md) | 機能仕様 + アーキテクチャ設計 | LLM / 設計レビュー |
| [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) | **本リポジトリの決定的仕様** (何を作るか・作らないか) | LLM / 開発者 |
| [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md) | 実装カタログ (ディレクトリ / ファイル / DB テーブル / API / GCP / Terraform) | 新規参加者 / LLM |
| [`docs/04_運用.md`](docs/04_運用.md) | 環境構築 + 定常運用 + インシデント対応 + ロールバック | 新規参加者 / 運用担当 |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 向け作業ガイド (非負制約 / 参照リポジトリ / feature-parity invariant) | Claude Code |

ドキュメントが互いに矛盾したときの勝者は `docs/02_移行ロードマップ.md` (詳細は `docs/README.md §2` 権威順位)。

## 品質ステータス

`make check` 全工程 PASS 目標 — ruff / ruff format / mypy strict / pytest。
`make tf-validate` PASS (offline)。
