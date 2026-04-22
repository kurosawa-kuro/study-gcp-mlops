# study-hybrid-search-vertex

BigQuery + Cloud Run に閉じた軽量 MLOps パイプライン — **不動産ハイブリッド検索 × LightGBM LambdaRank**。Meilisearch (lexical) + BigQuery VECTOR_SEARCH (semantic) + RRF fusion を採用し、キャッシュは `cachetools.TTLCache` の in-memory 構成で運用する `study-hybrid-search-vertex`。

> **スコープ**: 不動産検索 (クエリ文 + フィルタ → ランキング上位 20 件) のみ。旧 California Housing 回帰は削除済 (Phase 10b/10c)。

本 README は「機能の簡易説明 + 各ドキュメントへのリンク」だけを扱う (`docs/README.md` §1 の規約に従う)。環境構築・運用・実装詳細は下記 **§ ドキュメント** の各ファイルへ。

## アーキテクチャ

```
raw.properties (upstream ETL)
  └─ Dataform ─> feature_mart.properties_cleaned
                 feature_mart.property_features_daily (ctr / fav_rate / inquiry_rate)
                                   ↑ (+ assertions)
  └─ Vertex AI KFP `property-search-embed` pipeline (Vertex CPR encoder, multilingual-e5-base) ─> feature_mart.property_embeddings
                                                              ↑ (768d FLOAT64 REPEATED + VECTOR INDEX)
  └─ Vertex AI KFP `property-search-train` pipeline (LightGBM LambdaRank) ─> GCS (gs://mlops-dev-a-models/lgbm/{date}/{run_id}/) + mlops.training_runs + Vertex Model Registry

         └─ Cloud Run Service `search-api` (FastAPI)
              ├─ /search   Vertex Endpoint encoder + Meilisearch(BM25) + BQ VECTOR_SEARCH → RRF → Vertex Endpoint reranker
              │             └─ Pub/Sub "ranking-log"    ─> BQ Subscription ─> mlops.ranking_log
              ├─ /feedback └─ Pub/Sub "search-feedback" ─> BQ Subscription ─> mlops.feedback_events
              └─ /jobs/check-retrain / /events/retrain (Cloud Scheduler 04:00 JST → Eventarc → pipeline-trigger Cloud Function → PipelineJob)

  └─ Cloud Run Service `meili-search` (GCS FUSE `/meili_data` mount)

  └─ Scheduled Query 05:00 JST `property_feature_skew_check` ─> mlops.validation_results
       └─ Cloud Monitoring ログベースメトリクス + Looker Studio
```

## ディレクトリ

| パス | 役割 |
|---|---|
| `infra/` | Terraform — BQ / GCS / Pub/Sub / Cloud Run / Vertex (Endpoints, Pipelines, Feature Group, Monitoring) / Scheduler / Eventarc / WIF |
| `definitions/` | Dataform — `properties_cleaned` + `property_features_daily` + assertions |
| `ml/common/` | 共有コード — `BigQueryEmbeddingStore` / `build_ranker_features` / ranking metrics / logging / gcs (app と ml/ の両方から使う) |
| `app/` | Cloud Run Service `search-api` (`/search` / `/feedback` / `/jobs/check-retrain` / `/events/retrain`) |
| `ml/data/` | 埋め込み/ローダー系の実装 (`loaders`, `preprocess`, `feature_engineering`) |
| `ml/training/` | LambdaRank 学習本体 (`trainer`, `model_builder`, experiments) |
| `ml/serving/` | 推論補助ロジック (`predictor`, `response_builder`) |
| `pipeline/` | KFP エントリポイント (`data_job`, `training_job`, `evaluation_job`, `batch_serving_job`) |
| `scripts/local/` | deploy/setup/ops の運用コマンド群 |
| `monitoring/` | feature skew Scheduled Query SQL |
| `.github/workflows/` | CI (ruff/mypy/pytest) + Terraform + deploy-api / deploy-encoder-image / deploy-trainer-image / deploy-reranker-image / deploy-pipeline / deploy-dataform |
| `docs/` | 仕様と設計・移行ロードマップ・実装カタログ・運用 (+ ドキュメント運用ルール) |

ファイル単位の一言コメントは [`docs/03_実装カタログ.md §2`](docs/03_実装カタログ.md)。
注記: 本 Phase は Vertex/Cloud Run を実行基盤とするため、`docker-compose.yml` はルート直下に置かない。

## 設計ハイライト

詳細は [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) と [`docs/01_仕様と設計.md`](docs/01_仕様と設計.md)。

- **Vertex AI / PostgreSQL / Redis サーバ非採用**。候補抽出は Meilisearch(BM25) + BigQuery VECTOR_SEARCH を RRF で融合し、再ランクは LightGBM LambdaRank
- **Training-Serving Skew 対策**: Dataform SQL (`property_features_daily`) と `common.feature_engineering.build_ranker_features` を同一式で維持 (変更時は 5 ファイル同一 PR)
- **Phase 5 rerank-free MVP**: LightGBM booster を lifespan にロードしなくても `/search` は候補抽出 (`final_rank = lexical_rank`) を返せる。Phase 6 で rerank を bolt-on
- **認証**: Cloud Run Service は `--no-allow-unauthenticated`。CI は Workload Identity Federation (SA Key 不使用)
- **固定値**: プロジェクト `mlops-dev-a` / リージョン `asia-northeast1` / Python 3.12 / uv / Terraform 1.9

## デプロイ

`main` へのマージで path filter に応じて以下が走る:

| 変更 | 反応するワークフロー | 動作 |
|---|---|---|
| `infra/**` | `terraform.yml` | plan (PR コメント) → push で apply |
| `app/**`, `common/**` | `deploy-api.yml` | Docker build → Artifact Registry → `gcloud run deploy search-api` |
| `pipeline/data_job/**`, `ml/data/**`, `ml/common/**` | `deploy-encoder-image.yml` | Docker build → push Vertex CPR encoder image |
| `pipeline/training_job/**`, `ml/training/**`, `ml/common/**` | `deploy-trainer-image.yml` | Docker build → push KFP trainer image |
| `ml/serving/**`, `ml/common/**` | `deploy-reranker-image.yml` | Docker build → push Vertex CPR reranker image |
| `pipeline/**`, `scripts/local/setup/**` | `deploy-pipeline.yml` | KFP templates compile → upload to GCS + Model Monitoring + Schedule setup |
| `definitions/**` | `deploy-dataform.yml` | `dataform compile` + Dataform API へ compilationResults POST |

認証はすべて WIF。

## ドキュメント

初めてこのリポジトリに触る人は、まず [`docs/04_運用.md §1 環境構築`](docs/04_運用.md) の **STEP 1–17** を上から叩く。

| ドキュメント | 目的 | 主な読者 |
|---|---|---|
| [`docs/README.md`](docs/README.md) | ドキュメント運用ルール (役割 / 権威順位 / 更新規約 / 書き方) | 文書を触る人全員 |
| [`docs/01_仕様と設計.md`](docs/01_仕様と設計.md) | 機能仕様 + アーキテクチャ設計 | LLM / 設計レビュー |
| [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) | **本リポジトリの決定的仕様** (何を作るか・作らないか) | LLM / 開発者 |
| [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md) | 実装カタログ (ディレクトリ / ファイル / DB テーブル / API / GCP / Terraform) | 新規参加者 / LLM |
| [`docs/04_運用.md`](docs/04_運用.md) | 環境構築 (STEP 1–17) + 定常運用 + インシデント対応 + ロールバック | 新規参加者 / 運用担当 |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 向け作業ガイド (非負制約 / 参照リポジトリ / feature-parity invariant) | Claude Code |

ドキュメントが互いに矛盾したときの勝者は `docs/02_移行ロードマップ.md` (詳細は `docs/README.md §2` 権威順位)。

## 品質ステータス

`make check` 全工程 PASS — ruff / ruff format / mypy strict / pytest。
`make tf-validate` PASS (offline)。
