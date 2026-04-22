# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MLOps 学習 Phase 2。**題材は Phase 1 と同じ** カリフォルニア住宅価格予測（LightGBM 回帰）。Phase 1 の ML コアを引き継ぎつつ、**App (API 連携) / Pipeline (ジョブ分離) / Port-Adapter (依存方向の制御)** を導入する「デザインパターン導入 Phase」。

### Phase 1 → 2 の差分（何が新しく入るか）

| 要素 | Phase 1 | Phase 2 |
|---|---|---|
| モデル学習 | `pipeline/training_job` (スクリプト) | `pipeline/train_job` + Inbound Adapter (pipeline handler) → `ml/core` ユースケース呼び出し |
| 推論 | （Phase 1 には無くなった。Phase 2 新規） | `app/` FastAPI + Inbound Adapter (HTTP) → `ml/core` 予測ユースケース |
| データ取得 | `ml/data/loaders/repository.py` を直接 import | Outbound Port `DatasetReader` + Adapter `PostgresDatasetReader` |
| モデル保存/読込 | `ml/registry/artifact_store.py` を直接 import | Outbound Port `ModelStore` + Adapter `FilesystemModelStore` |
| 設定注入 | グローバル `BaseAppSettings` | `ml/container.py` で DI 配線 |
| パイプライン起動 | `pipeline/main.py` 1 ファイル | `pipeline/{seed,train,predict}_job/main.py` × 3 entrypoint |

Phase 1 のコア（`ml/training/trainer.py` / `ml/evaluation/` / `ml/data/preprocess` / `ml/data/feature_engineering`）は**そのまま**持ち込む。変えるのは「どう呼び出すか」だけ。

## Architecture — 3 層軽量 Port/Adapter

```
┌─ Inbound Adapters ─────────────────┐
│  app/api/*           (HTTP)         │
│  pipeline/*_job/main (CLI / job)    │
└────────────┬────────────────────────┘
             │ 呼び出し
             ▼
┌─ ml/core ──────────────────────────┐
│  trainer / evaluator / preprocess   │  純粋ロジック（I/O に依存しない）
│  feature_engineering                │
└────────────┬────────────────────────┘
             │ 抽象経由
             ▼
┌─ ml/ports (Protocol 定義のみ) ──────┐
│  DatasetReader                      │
│  ModelStore                         │
│  ExperimentTracker                  │
└────────────┬────────────────────────┘
             │ 実装
             ▼
┌─ ml/adapters (concrete 実装) ───────┐
│  PostgresDatasetReader              │
│  FilesystemModelStore               │
│  WandbExperimentTracker             │
└─────────────────────────────────────┘

ml/container.py ─ DI 配線（port ↔ adapter）、FastAPI lifespan / job entrypoint から参照
```

**依存方向ルール**（import は下方向のみ。逆流禁止）:
- `app/`, `pipeline/` → `ml/core`, `ml/container`
- `ml/core` → `ml/ports`（Protocol のみ、外部 SDK 非依存）
- `ml/adapters` → `ml/ports` を実装、外部 SDK（sqlalchemy / psycopg / wandb 等）使用可
- `ml/ports` → Python 標準のみ
- `ml/core` は `ml/adapters` を import しない

### Phase 3 (`3/study-hybrid-search-local`) への接続

本 Phase の Port/Adapter 3 層構造は Phase 3 でそのまま継承される。Phase 3 では adapters が Meilisearch / Redis / multilingual-e5 に差し替わり、**「adapter だけ差し替えて core は動く」を体感する教材**になる。本 Phase で `ml/ports` の粒度設計をミスると Phase 3 の移植コストが跳ねるため、**Port の引数/返り値は I/O 実装を想定しない pure-data（DataFrame / dataclass / primitive）で閉じる**。

## Source Layout（target）

```
2/study-ml-app-pipeline/
├── app/                    # Inbound Adapter (HTTP) — Phase 1 から migrate
│   ├── main.py             # FastAPI + lifespan (container 組み立て)
│   ├── config.py
│   ├── api/                # HTTP ルータ → inbound port 呼び出し
│   ├── schemas/            # API 専用 DTO
│   ├── services/           # 薄いオーケストレーション
│   ├── static/
│   └── templates/
├── ml/
│   ├── core/               # 純粋ロジック（Phase 1 の ml/training, ml/evaluation, ml/data/preprocess, ml/data/feature_engineering を統合）
│   │   ├── trainer.py
│   │   ├── evaluation.py
│   │   ├── preprocess.py
│   │   └── feature_engineering.py
│   ├── ports/              # Protocol 定義のみ（外部 SDK 非依存）
│   │   ├── dataset.py      # DatasetReader.load() -> DataFrame
│   │   ├── model_store.py  # ModelStore.save/load(run_id, path)
│   │   └── tracker.py      # ExperimentTracker.log_metrics(...)
│   ├── adapters/           # ports の具象実装
│   │   ├── postgres_dataset.py
│   │   ├── filesystem_model_store.py
│   │   └── wandb_tracker.py
│   └── container.py        # DI 配線（settings → adapters → container）
├── pipeline/               # Inbound Adapter (pipeline job) — entrypoint のみ
│   ├── seed_job/main.py
│   ├── train_job/main.py
│   └── predict_job/main.py
├── common/                 # settings / logging / schema / run_id
├── infra/
│   └── run/
│       ├── services/api/Dockerfile
│       └── jobs/trainer/Dockerfile
├── tests/
│   ├── unit/               # core / ports / adapters 単体
│   └── integration/        # api / pipeline 通し
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

## 非負制約（User 確認無しに変えない）

- **題材**: California Housing 回帰（Phase 1 から継承）
- **ランタイム**: Docker Compose（Phase 3 以降とは異なり、uv workspace ではない）
- **言語**: Python 3.10+（Phase 1 と同じ）
- **ML エンジン**: LightGBM（Phase 1 と同じ）
- **DB**: PostgreSQL 16（Phase 1 と同じ）
- **依存方向**: 上記 4 層依存図。AST / lint チェックは Phase 3 以降で追加予定、本 Phase は手動レビュー

## 現状（2026-04-22 時点）

**skeleton phase**。以下は Phase 1 から git mv 済み:
- `app/` — Phase 1 の FastAPI app
- `tests/integration/test_api.py`
- `infra/run/services/api/Dockerfile`
- `scripts/local/deploy/serve.py`

以下は今後実装:
- `ml/core/`, `ml/ports/`, `ml/adapters/`, `ml/container.py` — Phase 1 の `ml/*` をリファクタ
- `pipeline/{seed,train,predict}_job/main.py` — Phase 1 の `pipeline/*_job/` を port 呼び出し化
- `common/`, `docker-compose.yml`, `Makefile`, `pyproject.toml` — Phase 1 から複製して調整

Phase 1 からのコード複製方針：**Phase 1 `ml/*` をそのまま import せず、Phase 2 内に複製してから Port/Adapter に沿って切り分ける**（各 phase 独立原則）。
