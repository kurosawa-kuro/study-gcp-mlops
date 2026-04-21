# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MLOps教育用のカリフォルニア住宅価格予測パイプライン。LightGBM + Docker Compose でローカル完結する構成（Phase 1）。

## Architecture

```
PostgreSQL (docker-compose: postgres サービス / volume: postgres_data)
  → pipelines/housing_prices: Repository パターンでデータ取得
    → pipelines/housing_prices: 前処理 (欠損値補完・外れ値キャップ・対数変換)
      → pipelines/housing_prices: 特徴量エンジニアリング (BedroomRatio・RoomsPerPerson)
        → training: LightGBM 学習
          → training/evaluation: 精度評価 (RMSE, R²) + W&B ログ
            → ml/registry/artifacts/{run_id}/ に保存 + PostgreSQL に精度記録 + latest シンボリックリンク更新
              → app: FastAPI lifespan でモデルロード → 前処理 → 特徴量生成 → 推論
```

**Key design decisions:**
- **Docker 前提** — seed / train / serve は全て `docker compose` 経由で実行。DB も同じ network 上の `postgres` サービスを使用
- **パッケージ間の責務分離**: pipelines(データ+オーケストレーション) / training(学習) / training/evaluation(評価+W&B) / app(推論) / common(共通)
- **Repository pattern** — `PostgresRepository` (SQLAlchemy + psycopg)、`DATA_SOURCE` env var で切り替え
- **No scikit-learn for metrics** — RMSE, R² は numpy で自前実装 (`ml/evaluation/metrics.py`)
- **W&B はオプション** — API キーなしで offline モード動作。精度評価・モデル保存に影響なし
- **Run ID** — `YYYYMMDD_HHMMSS_{6桁UUID}` でモデルにバージョン付与。`ml/registry/artifacts/latest` シンボリックリンクで最新を参照
- **構造化ロギング** — `common/logging.py` の `get_logger()` で統一。全モジュール `logger.info()` を使用
- **API DI 化** — FastAPI lifespan で `app.state.booster` にモデルをロード。グローバル状態なし
- **エラーハンドリング** — pipeline/main.py でデータ取得・学習・W&B の各ステップを try-except で保護
- **Makefile → scripts/ に委譲** — `scripts/core.py` に共通設定を集約

## Source Layout

```
app/                  推論 API (FastAPI + Jinja2)
├── __init__.py
├── main.py           lifespan + /health, /predict, /metrics, /data
├── config.py
├── static/
└── templates/
pipeline/             データ取得 + 前処理 + 特徴量生成 + オーケストレーション
ml/                   ML コア
├── __init__.py
├── trainer/          LightGBM 学習
└── evaluation/       RMSE/R² 評価 + W&B 実験ログ
common/               共通定義
├── __init__.py
├── config.py         BaseAppSettings (YAML loader)
├── logging.py        get_logger
├── schema.py         FEATURE_COLS / ENGINEERED_COLS / MODEL_COLS / TARGET_COL
└── run_id.py         generate_run_id
tests/
├── conftest.py       共通フィクスチャ (sample_df / postgres_url / sample_db)
├── api/              FastAPI TestClient テスト
└── ml/               trainer / evaluation / pipeline / preprocess テスト
Dockerfile.api        api イメージ
Dockerfile.trainer    seed / trainer イメージ
```

## Commands

```bash
make build          # Docker イメージビルド
make seed           # sklearn データを PostgreSQL に投入 (Docker)
make train          # LightGBM 学習 → ml/registry/artifacts/{run_id}/ に保存 (Docker)
make serve          # FastAPI 起動 (port 8000, Docker)
make test           # pytest 全テスト実行 (ローカル)
make all            # build → seed → train
make down           # Docker Compose 停止
make clean          # Docker 停止 + 生成ファイル削除

# 単体テスト指定
python scripts/local/ops/test.py -k test_train
```

## Scripts

```
scripts/
├── core.py          共通設定 (credential 読み込み, compose 実行, step関数)
├── test.py          pytest (ローカル)
├── clean.py         Docker down + ファイル削除
├── ml/
│   ├── seed.py      docker compose run --rm seed (postgres サービス起動込み)
│   └── train.py     docker compose run --rm trainer
└── app/
    └── serve.py     docker compose up --build api
```

## Docker

| サービス | Image / Dockerfile | ポート | 用途 |
|---|---|---|---|
| postgres | postgres:16 | 5432 | データ永続化 (volume: `postgres_data`) |
| seed | `Dockerfile.trainer` | — | PostgreSQL データ投入 (run して終了) |
| trainer | `Dockerfile.trainer` | — | 学習 (seed 完了後に実行) |
| api | `Dockerfile.api` | 8000 | FastAPI 推論 + Web UI |

## Configuration

設定は用途別に 2 ファイルへ分離（どちらも YAML で統一）:

| ファイル | 内容 | git 管理 |
|---|---|---|
| `env/config/setting.yaml` | 非クレデンシャル（DB ホスト・ポート・DB 名・モデルパス等） | track |
| `env/secret/credential.yaml` | クレデンシャル（postgres_password, wandb_api_key） | **gitignore** (`env/secret/` ごと) |

`common/config.py::BaseAppSettings` が pydantic-settings の YamlConfigSettingsSource を 2 本積んで両方をロード。優先度: **環境変数 > credential.yaml > setting.yaml > コード既定値**。

**docker-compose 連携**: postgres コンテナ（公式イメージ）は env var で `POSTGRES_PASSWORD` を要求するため、`scripts/core.py::load_credentials` が起動前に credential.yaml を読み取り `POSTGRES_PASSWORD` / `WANDB_API_KEY` を process env に設定し、compose の `${POSTGRES_PASSWORD}` 補間で注入する。Python 側のコンテナは `./env/secret` を read-only volume でマウントし、BaseAppSettings が直接 YAML を読む。

### setting.yaml の主なキー

| キー | 用途 | 既定値 |
|---|---|---|
| `data_source` | データソース種別 | `postgres` |
| `postgres_host` | PostgreSQL ホスト | `postgres` (compose サービス名) |
| `postgres_port` | PostgreSQL ポート | `5432` |
| `postgres_db` | DB 名 | `mlpipeline` |
| `postgres_user` | DB ユーザー | `admin` |
| `model_dir` | モデル出力先 | `ml/registry/artifacts` |
| `model_path` | API が読むモデルパス | `ml/registry/artifacts/latest/model.lgb` |
| `wandb_project` | W&B プロジェクト名 | `california-housing` |

### credential.yaml の主なキー

| キー | 用途 |
|---|---|
| `postgres_password` | PostgreSQL パスワード |
| `wandb_api_key` | W&B API キー（空なら offline モード） |

## Dependencies

lightgbm, pandas, numpy, scikit-learn (データ取得のみ), wandb, pydantic-settings, fastapi, uvicorn, jinja2, sqlalchemy, psycopg[binary]

テスト用 (ローカル pytest): `testcontainers[postgres]` (一時 PostgreSQL をテスト中に起動)。未インストール時は DB 依存テストが skip される。

## Testing

pytest + `pyproject.toml` で設定。`pythonpath = ["."]`, `testpaths = ["tests"]`。

```
tests/
├── conftest.py              共通フィクスチャ (sample_df, postgres_url, sample_db)
├── api/
│   └── test_api.py          /health, /predict エンドポイント
└── ml/
    ├── test_evaluation.py   RMSE, R², save_metrics, W&B offline
    ├── test_trainer.py      LightGBM 学習 + run ID + symlink
    ├── test_pipeline.py     Settings, PostgresRepository (testcontainers)
    └── test_preprocess.py   前処理
```
