# study-llm-reranking-mlops

不動産検索ランキング基盤の学習用リポジトリです。

## Phase 0 実装済み範囲

- FastAPI の最小 API（health エンドポイント）
- Docker Compose によるローカル起動基盤
- PostgreSQL / pgAdmin / Meilisearch / Redis の連携雛形
- 初期ディレクトリ構成（現在は責務別に `api/clients/services/trainers/jobs/core/repositories` へ整理）

## Phase 1 実装済み範囲

- `properties` テーブル作成 SQL
- seed データ投入 SQL
- PostgreSQL から Meilisearch への同期バッチ
- `GET /search` 実装（絞り込み対応）

## Phase 2 実装済み範囲

- `search_logs` / `property_stats` テーブル作成 SQL
- 検索時ログ保存（query, user_id, result_ids）
- impression 自動加算
- `POST /feedback` 実装（click/favorite/inquiry）
- click 時の `search_logs.clicked_id` 更新

## Phase 3 実装済み範囲

- `property_features` テーブル作成 SQL
- `batch_job_logs` テーブル作成 SQL
- 日次バッチ（CTR/Fav/Inq再集計、特徴量更新、inactive除外）
- バッチ実行結果ログ保存（success/failed, processed_count）
- 特徴量レポート出力

## Phase 4 実装済み範囲

- `property_embeddings` テーブル作成 SQL
- `search_logs.me5_scores` カラム追加
- `property_features.me5_score` カラム追加
- 物件埋め込み生成バッチ（ME5、オフライン時はdeterministic fallback）
- `GET /search` でME5類似度計算と再ランキング
- 日次特徴量更新で `me5_score` 集計反映

## Phase 5 着手済み範囲

- 学習ログ拡張（`search_logs.actioned_id`, `search_logs.action_type`）
- 学習データ生成スクリプト（`ml/training/model_builder.py`）
- LightGBM 学習スクリプト（`ml/training/trainer.py`）
- `GET /search` への LightGBM 推論再ランキング統合（モデル未学習時はfallback）
- Meili順と再ランキング順の比較ログ出力（`ranking_compare_logs`）

## Phase 6 実装済み範囲

- オフライン評価（NDCG@10, MAP, Recall@20）
- オンライン KPI 日次集計（CTR, favorite_rate, inquiry_rate, CVR）
- 週次レポート出力（CSV/Markdown）
- モデル採用判定ルール（閾値ベース）
- `GET /search` の Redis キャッシュ（`SEARCH_CACHE_TTL_SECONDS`、既定 120 秒）

## テスト

- `app/tests/api/test_api.py`（`/health`, `/search`, `/feedback` の正常系）
- `common/tests/clients/test_redis_client.py`（キャッシュキー、hit/miss、障害時フォールバック）
- `tests/unit/pipeline/services/...`（検索・埋め込み・評価ロジック）
- 実行コマンド: `make test`

## ローカル開発セットアップ

1. Python 仮想環境を作成して有効化

	python3 -m venv .venv
	source .venv/bin/activate

2. ランタイム依存と開発依存をまとめて導入

	uv sync --dev

補足:

- 依存定義は `pyproject.toml` に統一されています
- `uv sync --dev` でランタイム + 開発依存を一括同期します
- Docker 実行だけでなくローカルで `pytest` を回す場合もこの手順を前提にします

## 起動

1. コンテナ起動

	make build
	make up

2. ヘルスチェック

	make ops-livez

3. 初期セットアップ（一括）

	make ops-bootstrap

4. 基本動作確認

	make ops-search
	make ops-feedback
	make ops-ranking

5. 定常運用

	make ops-daily
	make ops-weekly

6. 代表 E2E 確認

	make verify-pipeline

補足:

- 新規運用は責務ベースターゲット（`ops-sync`, `ops-embed`, `ops-train-build`, `ops-train-fit`, `ops-retrain`, `features-daily` など）を使用
- `make verify-pipeline` は `ops-livez` / `ops-search` / `ops-feedback` / `ops-ranking` / `ops-ranking-verbose` / `eval-compare` / `eval-offline` を順に実行します
- `app/common/jobs/pipelines` 配下の構成変更やブランチ切替後に API コンテナが古いイメージを参照していると import で失敗することがあります。その場合は次を実行して API イメージを再作成してください

	docker compose build api
	docker compose up -d --force-recreate api

## アクセス先

- FastAPI: http://localhost:8000
- pgAdmin: http://localhost:5050
- Meilisearch: http://localhost:7700
- PostgreSQL: localhost:5432

## 主要ファイル

- docker-compose: ./docker-compose.yml
- FastAPI entrypoint: ./app/main.py
- 非クレデンシャル設定: ./env/config/setting.yaml / クレデンシャル: ./env/secret/credential.yaml

## レイアウト互換レイヤ

依頼に合わせ、以下のターゲット寄せディレクトリを追加しています。
新構成を正とし、旧 `app/src/app` 互換レイヤは撤去済みです。

- app/api, app/services, app/schemas, app/main.py
- ml/data, ml/training, ml/evaluation, ml/registry, ml/serving, ml/common
- pipeline/data_job, pipeline/training_job, pipeline/evaluation_job, pipeline/batch_serving_job
- infra/terraform/modules, infra/terraform/environments, infra/run/jobs, infra/run/services
- docs/architecture, docs/operations, docs/decisions
- scripts/dev, scripts/ci, scripts/local
- tests/unit, tests/integration, tests/e2e
