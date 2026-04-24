# study-hybrid-search-cloud

BigQuery + Cloud Run に閉じた軽量 MLOps パイプライン — **不動産ハイブリッド検索 × LightGBM LambdaRank**。Meilisearch (lexical) + BigQuery VECTOR_SEARCH (semantic) + RRF fusion を採用し、キャッシュは `cachetools.TTLCache` の in-memory 構成で運用する。

> **スコープ**: 不動産検索 (クエリ文 + フィルタ → ランキング上位 20 件) のみ。旧 California Housing 回帰は削除済 (Phase 10b/10c)。

本 README は「機能の簡易説明 + 各ドキュメントへのリンク」だけを扱う (`docs/README.md` §1 の規約に従う)。環境構築・運用・実装詳細は下記 **§ ドキュメント** の各ファイルへ。

## アーキテクチャ

```
raw.properties (upstream ETL)
  └─ Dataform ─> feature_mart.properties_cleaned
                 feature_mart.property_features_daily (ctr / fav_rate / inquiry_rate)
                                   ↑ (+ assertions)
  └─ Cloud Run Jobs `embedding-job` (multilingual-e5-base) ─> feature_mart.property_embeddings
                                                              ↑ (768d FLOAT64 REPEATED + VECTOR INDEX)
  └─ Cloud Run Jobs `training-job`  (LightGBM LambdaRank) ─> GCS (gs://mlops-dev-a-models/lgbm/{date}/{run_id}/) + mlops.training_runs

         └─ Cloud Run Service `search-api` (FastAPI)
              ├─ /search   lifespan encoder + Meilisearch(BM25) + BQ VECTOR_SEARCH → RRF → rerank (Phase 6+)
              │             └─ Pub/Sub "ranking-log"    ─> BQ Subscription ─> mlops.ranking_log
              ├─ /feedback └─ Pub/Sub "search-feedback" ─> BQ Subscription ─> mlops.feedback_events
              └─ /jobs/check-retrain / /events/retrain (Cloud Scheduler 04:00 JST → Eventarc → training-job)

  └─ Cloud Run Service `meili-search` (GCS FUSE `/meili_data` mount)

  └─ Scheduled Query 05:00 JST `property_feature_skew_check` ─> mlops.validation_results
       └─ Cloud Monitoring ログベースメトリクス
```

## ディレクトリ

| パス | 役割 |
|---|---|
| `infra/` | Terraform と実行基盤定義。`terraform/environments/main` と `terraform/modules` に集約 |
| `definitions/` | Dataform — `properties_cleaned` + `property_features_daily` + assertions |
| `common/` | 共有コード — `BigQueryEmbeddingStore` / `E5Encoder` / `build_ranker_features` / ranking metrics / logging / gcs |
| `app/` | Cloud Run Service `search-api`。`app/api`, `app/services`, `app/schemas` を中心に配置 |
| `ml/` | 学習用の責務ベース構成。`data`, `training`, `evaluation`, `registry` が本体で、互換レイヤは持たない |
| `pipeline/` | `data_job` / `training_job` のトップレベル入口 |
| `monitoring/` | feature skew Scheduled Query SQL |
| `.github/workflows/` | CI (ruff/mypy/pytest) + Terraform + deploy-api / deploy-training-job / deploy-embedding-job / deploy-dataform |
| `docs/` | 仕様と設計・移行ロードマップ・実装カタログ・運用 (+ ドキュメント運用ルール) |

ファイル単位の一言コメントは [`docs/03_実装カタログ.md §2`](docs/03_実装カタログ.md)。
注記: 本 Phase 以降はクラウド実行 (Cloud Run/Terraform) が正系のため、`docker-compose.yml` はルート直下に置かない。

## 設計ハイライト

詳細は [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) と [`docs/01_仕様と設計.md`](docs/01_仕様と設計.md)。

- **Vertex AI / PostgreSQL / Redis サーバ非採用**。候補抽出は Meilisearch(BM25) + BigQuery VECTOR_SEARCH を RRF で融合し、再ランクは LightGBM LambdaRank
- **Training-Serving Skew 対策**: Dataform SQL (`property_features_daily`) と `common.feature_engineering.build_ranker_features` を同一式で維持 (変更時は 5 ファイル同一 PR)
- **Phase 4 rerank-free MVP**: LightGBM booster を lifespan にロードしなくても `/search` は候補抽出 (`final_rank = lexical_rank`) を返せる。Phase 6 で rerank を bolt-on
- **認証**: Cloud Run Service は `--no-allow-unauthenticated`。CI は Workload Identity Federation (SA Key 不使用)
- **固定値**: プロジェクト `mlops-dev-a` / リージョン `asia-northeast1` / Python 3.12 / uv / Terraform 1.9

## デプロイ

`main` へのマージで path filter に応じて以下が走る:

| 変更 | 反応するワークフロー | 動作 |
|---|---|---|
| `infra/**` | `terraform.yml` | plan (PR コメント) → push で apply |
| `app/**`, `common/**` | `deploy-api.yml` | Docker build (`infra/run/services/search_api/Dockerfile`) → Artifact Registry → `gcloud run deploy search-api` |
| `ml/training/**`, `common/**` | `deploy-training-job.yml` | Docker build (`infra/run/jobs/training/Dockerfile` + `infra/run/jobs/training/cloudbuild.yaml`) → push → `gcloud run jobs update training-job` |
| `ml/data/**`, `common/src/common/embeddings/**` 等 | `deploy-embedding-job.yml` | Docker build (`infra/run/jobs/embedding/Dockerfile` + `infra/run/jobs/embedding/cloudbuild.yaml`) → push → `gcloud run jobs update embedding-job` |
| `definitions/**` | `deploy-dataform.yml` | `dataform compile` + Dataform API へ compilationResults POST |

`common/**` は 3 ワークフロー (api / training-job / embedding-job) の対象に含める。`common/src/common/embeddings/**` は app (query encode) と embedding-job (passage encode) の共有コードなので `deploy-api.yml` / `deploy-embedding-job.yml` の両方が path filter に含める。認証はすべて WIF。

## 簡易精度評価レポート

`/search` の実レスポンスから、簡易な `nDCG@K / HitRate@K / MRR@K` を集計する運用スクリプトを追加した。

- GCP (Cloud Run): `make ops-accuracy-report`
- ローカル API: `make local-accuracy-report`

評価ケースは `scripts/local/data/accuracy_eval_cases.sample.json`。任意データを使う場合は `EVAL_CASES_FILE=/path/to/cases.json` を指定する。

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
