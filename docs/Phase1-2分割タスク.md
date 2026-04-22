# Phase 1 → Phase 1+2 分割タスク棚卸し

作成日: 2026-04-22

旧 Phase 1 (`study-ml-foundations`) を **ML 基礎に集中した新 Phase 1** と、**App / Pipeline / Port-Adapter を導入する新 Phase 2 (`study-ml-app-pipeline`)** に分割する作業の進捗と残タスク棚卸し。

---

## 0. 既完了（本セッション 2026-04-22）

### 0.1 ディレクトリ renumber（旧 Phase 2-4 → 新 Phase 3-5）
- [x] `git mv 4 5` / `git mv 3 4` / `git mv 2 3`（737 ファイル rename 済み）
- [x] ルート `CLAUDE.md` / `README.md` の「Phase N」表記・パス参照を増分
- [x] `docs/01_仕様と設計.md` / `docs/03_実装カタログ.md` / `docs/04_運用.md` / `docs/ランキング最適化ロジック/*.md` の Phase 番号更新
- [x] `3/study-hybrid-search-local/` `4/study-hybrid-search-cloud/` `5/study-hybrid-search-vertex/` の CLAUDE.md / README.md 内部 Phase 番号更新
- [x] ルート doc に「5 フェーズ構成」「Phase 2 新設予定」注記
- [x] ルート CLAUDE.md の「各 phase 独立 Git リポ」という stale 記述を「単一親 Git repo」に訂正

### 0.2 新 Phase 2 skeleton 新設
- [x] `2/study-ml-app-pipeline/CLAUDE.md`（設計テーゼ + 3 層依存図 + Source Layout）
- [x] `2/study-ml-app-pipeline/README.md`（位置付け + 学習ゴール）
- [x] `2/study-ml-app-pipeline/Makefile`（TBD stub）
- [x] `2/study-ml-app-pipeline/pyproject.toml`（Phase 1 から fastapi/uvicorn/jinja2 を継承）
- [x] 空ディレクトリ scaffold: `ml/core/` `ml/ports/` `ml/adapters/` `pipeline/{seed,train,predict}_job/` `tests/integration/` 等
- [x] 各 `__init__.py` / `main.py` stub（TBD docstring 付き、`NotImplementedError` raise）
- [x] `ml/container.py` stub

### 0.3 Phase 1 → Phase 2 移行（git mv 済みファイル）
- [x] `app/`（FastAPI + templates + static + services 全体）
- [x] `infra/run/services/api/Dockerfile`
- [x] `tests/integration/test_api.py`
- [x] `scripts/local/deploy/serve.py`

### 0.4 Phase 1 引き算（既完了）
- [x] `ml/serving/`（`__init__.py` / `predictor.py` / `batch_predictor.py` / `response_builder.py`）削除 — `app.services.prediction_service` への循環 import 依存
- [x] `scripts/local/deploy/`（空になった）削除
- [x] `Makefile` から `serve` target 削除
- [x] `pyproject.toml` から `fastapi` / `uvicorn[standard]` / `jinja2` / `httpx` 削除
- [x] `docker-compose.yml` から `api` service 削除
- [x] `scripts/core.py` の `HOST_PORTS` から `8000` 除外
- [x] `tools/check_docker_layout.py` REQUIRED から `infra/run/services/api/Dockerfile` 除外
- [x] `CLAUDE.md` 全面書き直し（「ML 基礎に集中」の説明、app/serving セクション削除）
- [x] `README.md` 全面書き直し（make serve / 推論 API / /predict の記述削除）
- [x] `docs/01_仕様と設計.md` 冒頭に「app / ml/serving は Phase 2 移管」注記
- [x] `docs/03_実装カタログ.md` から `## app` / `## ml/serving` セクション削除、scripts パス更新
- [x] `docs/04_運用.md` 基本フローから `make serve` 削除

---

## 1. 新 Phase 2 の未完項目

### 1.1 コア実装（Phase 1 からコピー）
- [ ] `ml/core/trainer.py` ← Phase 1 `ml/training/trainer.py` / `model_builder.py`
- [ ] `ml/core/evaluation.py` ← Phase 1 `ml/evaluation/metrics/regression.py` / `evaluation/report/tracking.py`
- [ ] `ml/core/preprocess.py` ← Phase 1 `ml/data/preprocess/preprocess.py`
- [ ] `ml/core/feature_engineering.py` ← Phase 1 `ml/data/feature_engineering/feature_engineering.py`
- [ ] `ml/core/schema.py` ← Phase 1 `ml/common/utils/schema.py`（FEATURE_COLS / ENGINEERED_COLS / MODEL_COLS / TARGET_COL）
- [ ] Phase 2 独立方針なので **import ではなくコピー**

### 1.2 Port 定義（`ml/ports/`）
- [ ] `dataset.py` — `DatasetReader` Protocol: `load(split: str) -> DataFrame`
- [ ] `model_store.py` — `ModelStore` Protocol: `save(run_id, model) -> path` / `load(run_id) -> Booster` / `set_latest(run_id)`
- [ ] `tracker.py` — `ExperimentTracker` Protocol: `start(run_id, config)` / `log_metrics(metrics)` / `finish()`
- [ ] **依存方針**: Python 標準 + typing のみ使用、外部 SDK は import しない

### 1.3 Adapter 実装（`ml/adapters/`）
- [ ] `postgres_dataset.py` — `DatasetReader` 実装（SQLAlchemy + psycopg、Phase 1 `PostgresRepository` 相当）
- [ ] `filesystem_model_store.py` — `ModelStore` 実装（`ml/registry/artifacts/{run_id}/`、`latest` symlink 管理）
- [ ] `wandb_tracker.py` — `ExperimentTracker` 実装（API key 未設定で offline 動作）
- [ ] **依存方針**: ports を implement、外部 SDK 使用可

### 1.4 DI 配線（`ml/container.py`）
- [ ] `build_container(settings) -> Container` 関数（純関数）
- [ ] `Container` dataclass（`dataset` / `model_store` / `tracker` 属性保持）
- [ ] `app.main::lifespan` と `pipeline.*_job.main` の両方から呼べる形

### 1.5 Pipeline job 実装（`pipeline/*_job/main.py`）
- [ ] `seed_job/main.py` — `build_container` → sklearn fetch → `container.dataset.write(frame)` 相当（現状は Phase 1 `pipeline/data_job/main.py` を参照）
- [ ] `train_job/main.py` — `container.dataset.load()` → `core.preprocess` → `core.feature_engineering` → `core.trainer.train` → `container.model_store.save` → `container.tracker.log_metrics`
- [ ] `predict_job/main.py` — `container.model_store.load(run_id)` → `core.trainer.predict` → 結果を dataset に書き戻す

### 1.6 App 側の書き換え（移送済み `app/` の import 修正）
- [ ] `app/main.py` の `from ml.common.logging.logger import get_logger` / `from ml.common.utils.schema import FEATURE_COLS, TARGET_COL` / `from ml.data.loaders.config import Settings` / `from ml.data.loaders.repository import get_repository` を Phase 2 の新構造（`ml/core`, `ml/container`）に差し替え
- [ ] `app/config.py` の `from ml.common.config.base import BaseAppSettings` を差し替え（`common/` か `ml/core/` に置く）
- [ ] `app/services/prediction_service.py` の `ml.common.utils.schema` / `ml.data.feature_engineering` / `ml.data.preprocess` import を `ml.core` に差し替え
- [ ] FastAPI lifespan で `app.state.container = build_container(settings)` + `app.state.booster = container.model_store.load(latest)` 形式に
- [ ] `app/api/predict.py` で `container.predictor.predict(...)` 呼び出しに切り替え

### 1.7 環境/インフラ
- [ ] `common/` パッケージ新設（`config.py` / `logging.py` / `run_id.py`）
  - Phase 1 の `ml/common/` をコピー（Phase 2 独立のため）
  - Phase 1 との parity を保つ（schema / 設定キー名）
- [ ] `env/config/setting.yaml` / `env/secret/credential.yaml` 新設（Phase 1 からコピー）
- [ ] `docker-compose.yml` 新設（postgres / seed / trainer / api の 4 service）
- [ ] `infra/run/jobs/trainer/Dockerfile` 新設（Phase 1 からコピー）
- [ ] `ml/registry/artifacts/` .gitkeep（アーティファクト保存先）
- [ ] `.gitignore`（Phase 1 からコピー調整）
- [ ] `.python-version`（Phase 1 相当）

### 1.8 Makefile 本実装
- [ ] Phase 1 の Makefile パターンを踏襲（`build` / `seed` / `train` / `serve` / `test` / `all` / `down` / `clean` / `free-ports`）
- [ ] `scripts/local/setup/seed.py` / `train.py` / `scripts/local/deploy/serve.py` / `scripts/local/ops/{test,clean}.py` を整備
- [ ] `scripts/core.py`（Phase 1 からコピー）

### 1.9 テスト
- [ ] `tests/conftest.py`（sample_df / postgres_url / sample_db フィクスチャを Phase 1 から複製）
- [ ] `tests/unit/ml/core/` — trainer / evaluation / preprocess / feature_engineering テスト複製
- [ ] `tests/unit/ml/adapters/` — 各 adapter の testcontainers / tmp_path ベース単体テスト
- [ ] `tests/unit/ml/container.py` テスト — 配線の smoke
- [ ] `tests/integration/test_api.py`（既に移送済み、import 修正必要）
- [ ] `tests/integration/test_pipeline.py`（Phase 1 から複製 + container-based に書き換え）

### 1.10 ドキュメント（Phase 2 内）
- [ ] `docs/01_仕様と設計.md`（Port/Adapter の図 + import ルール）
- [ ] `docs/04_運用.md`（Phase 1 と同じ make フロー + serve）
- [ ] `docs/教育資料/`（動画台本はスコープ外、骨子のみ）

---

## 2. 新 Phase 1 の残タスク（引き算 / 内部整理）

### 2.1 残 ML モジュール内の整合性
- [ ] `ml/common/` の役割再確認 — Phase 1 単体で閉じるか、他 phase にも共通の基礎か決める
- [ ] `pipeline/batch_serving_job/main.py` の扱い — Phase 1 は推論を持たない方針なので削除検討（現状 stub）
- [ ] `pipeline/workflow/orchestration.md` の内容見直し（app 除外後の流れ）

### 2.2 ドキュメント追い込み
- [ ] `docs/01_仕様と設計.md` 本体の書き直し — 現状は冒頭注記のみ。アーキ章の `app` / `ml/serving` 記述は stale
- [ ] `docs/教育資料/制作メモ/01_構成タイムライン.md` から `make serve` 等の誤記削除（動画台本要素は後日）
- [ ] `docs/教育資料/制作メモ/03_ナレーション要約.md` 等、FastAPI 言及箇所の扱い — 教育動画作り直しのタイミングで整理
- [ ] `docs/教育資料/assets/diagram2_pipeline.svg` の FastAPI 部分（SVG 手作業修正 or 再書き出し）

### 2.3 tests
- [ ] `tests/conftest.py` — 移送した test_api.py 用のフィクスチャ（postgres_url 等）が Phase 2 にも必要。Phase 1 の conftest は `sample_df` 等 ML 系だけでも動くか確認
- [ ] 現在残っているテスト: `tests/unit/ml/{test_trainer,test_evaluation,test_preprocess}.py` + `tests/integration/test_pipeline.py`。これらが collectable で PASS することを実行確認（未実施）

### 2.4 動作確認（未実施）
- [ ] `make build && make seed && make train && make test` が通ることを確認
- [ ] `docker-compose.yml` から api service 除外後の build / up が通ること

---

## 3. Phase 1 → Phase 2 の**双方**に跨るオープン課題

### 3.1 アーティファクト共有
- [ ] Phase 1 で学習したモデル（`ml/registry/artifacts/latest/`）を Phase 2 API が読む想定だが、**物理的にどう繋ぐか未決**
  - 案 A: Phase 2 の docker-compose で Phase 1 の artifacts を read-only volume マウント
  - 案 B: Phase 2 で独立に学習する（Phase 1 は純教材で artifacts を共有しない）
  - 推奨: **案 B**（各 phase 独立原則と整合、Phase 2 は学習 → 推論まで自己完結）

### 3.2 Phase 1 と Phase 2 のコード重複
- [ ] ML コア（trainer / evaluation / preprocess / feature_engineering）を Phase 1 と Phase 2 が**両方持つ**構造になる
  - 利点: 各 phase 独立、差分 PR で phase ごとの学習ポイントが明確
  - 欠点: 同じバグを 2 箇所で直す可能性。ただし教材用途なので許容
  - 合意事項: **コピー方針で合意済み**（Phase 2 CLAUDE.md に明記）

### 3.3 `ml/common/` の命名衝突
- [ ] Phase 1 は `ml/common/` を持つ。Phase 2 も `common/` を作る想定だが、配置が `ml/common/` か root `common/` か要決定
  - Phase 1 は `ml/common/` (ml 配下)
  - Phase 2 提案構造は root `common/`（CLAUDE.md 記載）
  - 統一するなら両方を root `common/` に寄せる（小さな breaking だが Phase 2 のみ）

### 3.4 Phase 3 への繋ぎ
- [ ] Phase 2 の Port 粒度（特に `DatasetReader` の引数・返り値）が Phase 3 の `CandidateRetriever` / `CacheStore` 等と**思想的に整合**しているか、Phase 3 の CLAUDE.md と照合して確認
- [ ] Phase 3 の `uv workspace` 方式と Phase 2 の Docker Compose 方式の段差 — 教材としての意図を README で明示

---

## 4. commit 分割の提案（未実行）

- (A) 1 コミット: doc 番号書き換え + Phase 2 skeleton + Phase 1 trim
- (B) 2 コミット: ①doc 番号書き換え、②Phase 2 skeleton + Phase 1 trim
- (C) 3 コミット: ①doc 番号書き換え、②Phase 2 skeleton 新設、③Phase 1 trim
- **推奨**: (C) — レビュー単位が揃うため。番号書き換えは機械的、skeleton 追加は新規作成、trim は既存削除・更新で性質が異なる
