# study-hybrid-search-local

不動産ハイブリッド検索を題材に、ローカル環境で MLOps パイプラインを学ぶリポジトリです。  
Meilisearch (lexical) + ME5 (semantic) + LightGBM LambdaRank (rerank) の 3 段構成を、`docker-compose.yml` 前提で検証します。

> **スコープ**: ローカル完結の検索/学習/評価。クラウド実行基盤 (Cloud Run/BigQuery/Vertex) への展開は Phase 4/5 で扱います。

## アーキテクチャ

```
PostgreSQL (properties / logs / features / eval tables)
  └─ pipeline/batch (maintenance/features/evaluation batch)
       ├─ migrations / daily features / KPI / reports
       └─ DB 保守・特徴量更新・評価ジョブ

ml/
  ├─ data    : 前処理・特徴量生成・embedding 補助
  ├─ training: LightGBM LambdaRank 学習・再学習
  └─ serving : 検索/再ランキング補助

app (FastAPI)
  ├─ /search   : lexical + semantic + rerank
  ├─ /feedback : click/favorite/inquiry 収集
  └─ /health   : livez
```

## ディレクトリ

| パス | 役割 |
|---|---|
| `app/` | FastAPI API。`/search` / `/feedback` / `/health` を提供 |
| `common/` | 共通コード（ports/clients/dto/core） |
| `ml/` | ML コア処理。`data` / `training` / `evaluation` / `serving` / `registry` / `common` |
| `pipeline/batch/` | 非 ML バッチ。`maintenance` / `features` / `evaluation` |
| `pipeline/` | `data_job` / `training_job` / `evaluation_job` / `batch_serving_job` / `workflow` |
| `definitions/` | PostgreSQL migration SQL |
| `infra/` | `terraform` / `run` 定義（ローカルでは compose 前提） |
| `scripts/` | `ci` / `dev` / `local` の運用スクリプト |
| `docs/` | 仕様・移行計画・実装カタログ・運用・教育資料 |

注記: 本 Phase はローカル運用 (PostgreSQL/Meilisearch/Redis) を主目的とするため、`docker-compose.yml` をルート直下に保持します。

## デプロイ

本 Phase のデプロイはローカル実行のみを対象とし、`docker-compose.yml` を正とします。

- `make build` / `make up` / `make down` でコンテナライフサイクルを管理
- `make ops-bootstrap` で初期構築（migration + seed + 初回学習）を一括実行
- `make ops-daily` / `make ops-weekly` で定常運用タスクを実行

## ドキュメント

| ドキュメント | 目的 |
|---|---|
| `docs/01_仕様と設計.md` | 検索・学習・運用の設計方針 |
| `docs/02_移行ロードマップ.md` | Phase 内の実装計画と変更履歴 |
| `docs/03_実装カタログ.md` | ディレクトリ/ファイル/テーブル/API 一覧 |
| `docs/04_運用.md` | ローカル運用手順（日次/週次/障害対応） |

## テスト

- `app/tests/api/test_api.py`（`/health`, `/search`, `/feedback` の正常系）
- `common/tests/clients/test_redis_client.py`（キャッシュキー、hit/miss、障害時フォールバック）
- `tests/unit/pipeline/...`（usecase / services の検索・埋め込み・評価ロジック）
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
- `app/common/pipeline/ml` 配下の構成変更やブランチ切替後に API コンテナが古いイメージを参照していると import で失敗することがあります。その場合は次を実行して API イメージを再作成してください

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
- 注記: 本 Phase はローカル運用 (PostgreSQL/Meilisearch/Redis) を主目的とするため、`docker-compose.yml` をルート直下に保持する。

## レイアウト整理方針

責務別ディレクトリ構成を正とし、旧構成レイヤは保持しません。

- app/api, app/services, app/schemas, app/main.py
- ml/data, ml/training, ml/evaluation, ml/registry, ml/serving, ml/common
- pipeline/data_job, pipeline/training_job, pipeline/evaluation_job, pipeline/batch_serving_job
- infra/terraform/modules, infra/terraform/environments, infra/run/jobs, infra/run/services
- docs/ (番号付きファイル + 教育資料)
- scripts/dev, scripts/ci, scripts/local
- tests/unit, tests/integration, tests/e2e
