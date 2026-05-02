残タスク (本停止点で未着手)
Stage 1.1 / 1.2: Phase 7 docs (docs/01 §3 / TASKS_ROADMAP.md §4.7 / TASKS.md / CLAUDE.md) と親 docs (CLAUDE.md / README.md) を「Phase 7 canonical 起点」に書換
Stage 2: 3 DAG (pipeline/dags/) + composer_deploy_dags.py + Make target + deploy_all.py 15 step 化 + DAG unit tests
Stage 3: enable_composer=true flip + 軽量 trigger 格下げ + live make deploy-all 完走確認 + W2-8 統合 live re-verify
現在の enable_composer=false default のため、既存 make deploy-all の挙動は完全に変わっていません (Composer リソースは plan に出るが count=0 で no-op)。Stage 2 着手前に user の判断を待ちます。

/home/ubuntu/.claude/plans/unified-cuddling-tome.md

# 02. 移行ロードマップ — 検索アプリを最新仕様へ

Phase 7 の現コードを、最新仕様 (親 [README.md](../../../../README.md) §1-§3 / 親 [docs/01_仕様と設計.md](../../../../docs/architecture/01_仕様と設計.md) / 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md)) に追従させるための移行計画。

> **方針**: **Wave 1 = 検索アプリ自体 (app / ml / pipeline コード)** を先に整える。**Wave 2 = GCP インフラ (Terraform / IAM / deploy)** はその後。Wave 3 は docs / reference architecture との整合確認のみ (コード変更なし)。
>
> Port / Adapter / DI 大枠の整理は [`docs/TASKS_ROADMAP.md`](TASKS_ROADMAP.md)、過去の制約決定は [`docs/decisions/`](../decisions/README.md) を参照。
>
> **教育コード原則**: 後方互換・legacy fallback・旧 env 名 alias・旧 UI redirect・使われない shell resource は残さない。移行の都合で一時導入した互換レイヤも、役目を終えた時点で削除する。

---

## 進捗サマリ (2026-05-02 時点)

| Wave | フェーズ | 状態 | 要点 |
|---|---|---|---|
| Wave 1 | ローカル完結 (検索アプリ層) | ✅ 完了 | PR-1〜PR-4 merge、関連 mypy / pytest 63 passed |
| Wave 2 | GCP インフラ層 | 🟢 進行中 | W2-1 / 2 / 3 / 5 / 6 / 7 は live wiring 完了、`make run-all-core` 完走 (`ndcg_at_10=1.0`)。残: W2-8 互換レイヤ削除、W2-4 Composer Stage 2/3、live parity、本当の最後の `destroy-all` |
| Wave 3 | docs / reference architecture 整合 | 🟡 一部進行中 | `04_検証.md` / `05_運用.md` 更新済。残: `01_仕様と設計.md` / `03_実装カタログ.md` を W2-8 と同期 |

## 現在地サマリ (2026-05-02)

### 今できていること

- `make run-all-core` 完走
- `/search` canonical 経路で 200
- `ops-vertex-vector-search-smoke` / `ops-vertex-feature-group` / `ops-train-now` + `ops-train-wait` PASS
- `destroy-all -> deploy-all -> run-all-core` まで再現済

### 残り作業

- W2-8 互換レイヤ削除
- W2-4 Composer Stage 2 / 3
- `tests/integration/parity/*` の live 実行
- 最後の `destroy-all`

### 補足

- `deploy-all` の主な長待機は VVS deployed index attach (2026-05-02 実測 26m21s)
- `SEARCH_RETRIES` は safety net として残置
- 完了条件は `destroy-all -> deploy-all -> run-all-core -> destroy-all`

### 実測メモ

- live で確認済み: `ops-livez` / `ops-search` / `ops-search-components` / `ops-vertex-vector-search-smoke` / `ops-vertex-feature-group` / `ops-feedback` / `ops-ranking` / `ops-train-now` / `ops-train-wait` / `ops-label-seed` / `ops-daily` / `ops-accuracy-report`
- 代表値: `lexical=1 semantic=3 rerank=5`、`ndcg_at_10=1.0 hit_rate=1.0 mrr=1.0`
- 主要修正は deploy-all step 拡張、ConfigMap overlay 自動注入、provider の kubeconfig 化、FOS lifecycle 安定化、destroy-all parity 修正

---

## 0. 前提と非負ルール (作業前に必ず確認)

- **中核 5 要素は不変**: Meilisearch BM25 / multilingual-e5 / ベクトルストア (Phase 4 = BQ `VECTOR_SEARCH` / Phase 5+ = Vertex AI Vector Search) / RRF / LightGBM LambdaRank
- **Phase 7 の canonical 挙動は 1 本にする**: `/search` の本線は Vertex Vector Search + Feature Online Store とし、BigQuery fallback や backend 切替スイッチを最終形に残さない
- **embedding 生成履歴・メタデータの正本は BigQuery 側**: Vertex Vector Search は本番 serving index、source は BQ embedding テーブル (`feature_mart.property_embeddings`)
- **Feature Store (Phase 5 必須)** を Phase 7 でも継承: training-serving skew 防止のため、Feature Online Store 経路を canonical とする
- **Meilisearch / Redis 同義語辞書は据え置き**: 実案件 reference architecture (Elasticsearch + Redis 同義語辞書) を教材向け substitute で維持しつつ、本 phase でも中核コードの意味を崩さない
- **Feature parity invariant 6 ファイル原則** は SemanticSearch / FeatureFetcher 変更でも継続 PASS
- **Cloud Composer は Phase 6 で導入 (本線昇格 + PMLE DAG 増設)、Phase 7 で継承**: Phase 6 で `daily_feature_refresh` / `retrain_orchestration` / `monitoring_validation` の 3 本 DAG が orchestration 本線になり、PMLE step (Dataflow / BQML / SLO / Explainability) も同 DAG に増設される。Vertex `PipelineJobSchedule` は Phase 6 で完全撤去、Cloud Scheduler / Eventarc / Cloud Function trigger は本線から軽量代替へ格下げ (= Phase 5 → 6 引き算境界)。Phase 5 では Composer は導入せず、Phase 4 軽量経路を本線として継続。Phase 7 はそのまま継承し、orchestration 二重化を作らない (詳細は親 [`README.md` §「Cloud Composer の位置づけ」](../../../../README.md))。Wave 2 GCP インフラの中で Composer 関連 (Composer 環境 Terraform 継承確認 + DAG deploy) も含む

---

## 1. 現状コードと仕様のギャップ

✅ = Wave 1 で解消済 / ⏳ = Wave 2 / 3 で対応予定。

| 状態 | 観点 | 現状コード (Wave 1 前) | 最新仕様 (target) | 対応 |
|---|---|---|---|---|
| ✅ | Semantic 検索 adapter | [`bigquery_semantic_search.py`](../app/services/adapters/bigquery_semantic_search.py) のみ (BQ `VECTOR_SEARCH`) | Vertex AI Vector Search を本番 serving index にする (Phase 5+ 仕様) | **PR-1 完了**: [`vertex_vector_search_semantic_search.py`](../app/services/adapters/vertex_vector_search_semantic_search.py) 新規追加、BQ adapter 据え置き |
| ✅ | `SemanticSearch` 切替 | composition_root に backend 切替なし、常に BQ | Vertex Vector Search を canonical とし、暫定切替を撤去する | **PR-1 完了**: [`SearchBuilder._resolve_semantic_search`](../app/container/search.py) で暫定分岐を導入。**Wave 2 で削除対象** |
| ✅ | Feature 取得 (rerank 入力) | `BigQueryCandidateRetriever._enrich_from_bq` 内 SQL JOIN で direct fetch | Phase 5 で Feature Online Store 経由可能に (training-serving skew 防止) | **PR-2 完了**: [`FeatureFetcher`](../app/services/protocols/feature_fetcher.py) Port + 2 adapters + fake、PR-4 で Container 配線 |
| ✅ | Feature Online Store 統合 | 未実装 | Feature View 経由で fresh feature を取得する | **PR-4 完了**: `Container.feature_fetcher` + `SearchService` + `run_search` の `_augment_with_fresh_features` で merge。**Wave 2 で旧 BQ 経路削除対象** |
| ✅ | Embed pipeline の出力先 | `feature_mart.property_embeddings` (BQ) のみ | BQ + Vertex Vector Search index 双方に書く (BQ は正本、VVS は serving index) | **PR-3 完了**: [`upsert_vector_search`](../pipeline/data_job/components/upsert_vector_search.py) component + [`VectorSearchWriter`](../pipeline/data_job/ports/vector_search_writer.py) Port + 2 adapters。runner 側 gate (`vector_search_index_resource_name=""` で no-op) |
| ✅ | Vector Search Terraform モジュール | [`infra/terraform/modules/vector_search/`](../../infra/terraform/modules/vector_search/) ディレクトリは存在するが空 | `google_vertex_ai_index` + `google_vertex_ai_index_endpoint` + deployed index | **W2-1 完了**: module 実装 + `environments/dev/main.tf` で `module "vector_search"` 呼出し。live で `find_neighbors` PASS (deployed index attach 26m21s) |
| ✅ | Feature Online Store Terraform | 既に [`modules/vertex/main.tf:273`](../../infra/terraform/modules/vertex/main.tf) に資源定義あり、`enable_feature_online_store` default = `false` | Phase 5 必須要素なので default `true` 化、ただし `mlops-dev-a` の PDCA 都合で env 切替可能 | **W2-2 + #11 完了**: `enable_feature_online_store` / `enable_vector_search` の default を `true` に flip。`make destroy-all` 運用でコスト管理。FOS Optimized lifecycle.ignore_changes 追加で plan 安定 |
| ⏳ | docs reference architecture (Elasticsearch / Redis 同義語辞書) | コードに無い (✓ 期待通り) | 実装しない (docs only) | **Wave 3** で lint 化 — 2026-05-02 終端の grep では `Elasticsearch` / `synonym` / `query expansion` の固有名混入は無し。docs/01 / docs/03 の最終整合は W2-8 削除と同期 |

---

## 2. 移行戦略

### 2.1 暫定互換レイヤの扱い

Wave 1 ではローカル完結のために一時的な backend 切替と fallback を導入したが、**教育コードの完成条件はそれらを削除すること**。`BigQuerySemanticSearch` / `BigQueryFeatureFetcher` / backend 切替 env / legacy alias は Wave 2 の live 検証後に撤去し、Phase 7 の canonical 実装を 1 本に収束させる。

### 2.2 PR 分割粒度 (1 PR = 1 Port 原則)

| PR | スコープ | 受け入れ条件 |
|---|---|---|
| PR-1 | `SemanticSearch` Port + Vertex Vector Search adapter (app 層) + fake / unit test | `SEMANTIC_BACKEND=vertex_vector_search` で `/search` が in-memory fake 経由で 200 を返す |
| PR-2 | `FeatureFetcher` Port + Feature Online Store adapter (app 層) + fake | `FEATURE_FETCHER_BACKEND=online_store` で ranking が fake 経由で動作 |
| PR-3 | `VectorSearchWriter` Port + adapter (pipeline 層) + embed pipeline 二重書き | `pipeline/data_job/main.py` がローカルで BQ + fake VVS の両方に書く |
| PR-4 | Feature Online Store 統合 (Phase 7 固有) | Feature View 経由の fresh feature 取得が動作する |
| Wave 2 → | Terraform / IAM / deploy | 別 roadmap section §4 参照 |

### 2.3 互換レイヤ撤去の段取り

```
Step A: Wave 1 で live 以外の wiring を先に完成
Step B: Wave 2 で GCP apply / smoke / parity を完了
Step C: BigQuery fallback / backend 切替 env / legacy alias / 旧 shell resource を削除
Step D: docs/01, docs/03, docs/05 を canonical 実装 1 本に更新
```

### 2.4 ローカル完結スコープ (まず取りかかる範囲)

> **Wave 1 のコード変更はすべてローカル完結で書ける**。実 GCP 通信を伴う検証は Wave 2 で provision された後にまとめて行う。Wave 1 の受け入れ条件 (`make check` / `make check-layers` / unit test / in-memory fake 経由の `/search`) はすべて GCP 認証無しで成立する。

| PR | コード作業 | ローカル検証 | GCP 必要な部分 (Wave 2 で実施) |
|---|---|---|---|
| PR-1 SemanticSearch | adapter / settings / composition / fake / unit test の追加 — 全てローカル可 | `SEMANTIC_BACKEND=vertex_vector_search` + in-memory fake で `/search` 200 / mock で `find_neighbors` を呼ぶ unit test | live `aiplatform.MatchingEngineIndexEndpoint.find_neighbors` smoke (Wave 2 で `VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID` 投入後) |
| PR-2 FeatureFetcher | Port / 2 adapter / fake / `ranking.py` 改修 — 全てローカル可 | `FEATURE_FETCHER_BACKEND=online_store` + fake fetcher で ranking 動作 | live `FeatureOnlineStoreServiceClient.fetch_feature_values` smoke |
| PR-3 VectorSearchWriter | Port / 2 adapter / pipeline component 改修 — 全てローカル可 | `pipeline/data_job/main.py` を fake adapter (BQ も fake) で完走 | live `MatchingEngineIndex.upsert_datapoints` smoke + 初回 backfill |
| PR-4 Feature Store integration | adapter / settings / manifest env 追加 — 全てローカル可 (manifest apply は Wave 2) | unit test で fresh feature merge を確認 | live search-api 経路での Feature View 参照 smoke |

**ローカル開発前提**:

- Python 3.12 + `uv sync` で全依存解決済 (`google-cloud-aiplatform` は `pyproject.toml` に既存)
- `gcloud auth application-default login` は **不要** (mock / fake で完結)
- Docker 不要 (Meilisearch / Vertex SDK 通信は fake で stub)
- `make check` (ruff / format / mypy / pytest) は WSL ローカルで完走する前提

**ローカル完結の境界線**:

- `app/services/adapters/vertex_vector_search_semantic_search.py` の中身で Vertex SDK を import するのは OK。**実通信せず**、unit test で SDK call を mock して PASS させる
- `tests/integration/parity/` 配下の "live GCP 比較" テストは Wave 2 まで `pytest -m 'not live_gcp'` でスキップ可能なよう marker を付与する
- Wave 1 で導入した切替 env は **最終的に削除する**。教育コードでは「default off のまま残す」は許容しない

---

## 3. Wave 1 — 検索アプリ層 (本 roadmap の主タスク)

### 3.1 Wave 1 実装済み項目

Wave 1 の実装済み内容は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を正本とするため、ここでは重複記載しない。

残:
- [ ] `tests/integration/parity/test_semantic_backend_parity.py` の live 実行
- [ ] `tests/integration/parity/test_feature_fetcher_parity.py` の live 実行
- [ ] Cloud Logging ベースの eventual consistency 観測
- [ ] W2-8 で `SEMANTIC_BACKEND` / `FEATURE_FETCHER_BACKEND` / BQ fallback / 旧 enrich 依存を削除
- [ ] KFP 2.16 import 互換 issue の根本対処

---

## 4. Wave 2 — GCP インフラ層 (Wave 1 完了後 = 着手可能、**クラウド側の主作業計画**)

> **Wave 1 のローカル完結が完了したので、Wave 2 は GCP リソース provision に集中できる。**
> Wave 1 の検証残課題 (live GCP smoke、KFP 2.16 互換 issue) もここで吸収する。
>
> **位置付け**: 本セクションは **クラウド側 (GCP インフラ) の修正作業計画の母艦**。親 [`README.md`](../../../../README.md) は教育設計、本 phase [`docs/01_仕様と設計.md`](../architecture/01_仕様と設計.md) は仕様 canonical、本セクションが **「いつ何を Terraform / kubectl / gcloud で叩くか」の作業計画** を持つ。

### 4.0 Wave 2 実施順序 (時系列俯瞰)

GCP リソースの依存関係に従って以下の順序で進める。各 step は前段が完了するまで開始できない:

| Step | スコープ | サブセクション | 依存 | 観測される変化 |
|---|---|---|---|---|
| **W2-1** | Vertex Vector Search Terraform 実装 + apply | §4.1 | — | Index endpoint provision、index ID 出力 |
| **W2-2** | Feature Online Store default flip (`enable_feature_online_store=true`) + Feature View provision | §4.1 | — | Feature View ID 取得、regional public endpoint URL 取得 |
| **W2-3** | IAM / Workload Identity bind (KServe SA + Pipeline SA に Vertex Vector Search query / Feature View read 権限) | §4.2 | W2-1 / W2-2 | search-api / KServe pod が VVS / FOS に access 可能に |
| **W2-4** | Composer 本実装 (Phase 7 = canonical 起点。`infra/terraform/modules/composer/` + 3 DAG + `composer-deploy-dags` + `deploy_all` 15 step) | §4.7 | W2-1 / W2-2 / W2-3 | Composer 環境作成、3 DAG (`daily_feature_refresh` / `retrain_orchestration` / `monitoring_validation`) deploy |
| **W2-5** | Manifest env vehicle 追加 (search-api ConfigMap に暫定 backend 切替 env を追加し、live 検証後に撤去準備) | §4.3 | W2-1 / W2-2 | env 投入準備完了 |
| **W2-6** | 初回 backfill (`scripts/setup/backfill_vector_search_index.py` で `feature_mart.property_embeddings` → VVS index) | §4.4 | W2-1 / W2-3 | VVS index に既存 embedding 投入完了 |
| **W2-7** | smoke 確認 (`/search` が `SEMANTIC_BACKEND=vertex_vector_search` env で 200、live `find_neighbors` 経由) | §4.4 / §4.5 | W2-3 / W2-5 / W2-6 | live GCP smoke PASS、parity test PASS |
| **W2-8** | 互換レイヤ撤去 (backend 切替 env / BQ fallback / legacy alias を削除し、PMLE 4 技術 + Composer-managed BQ monitoring query が canonical 経路で動作確認) | §4.6 | W2-7 + 1 週間 dev 安定 | M6 達成 (search-api / pipeline が canonical 1 経路、本線 retrain は Composer DAG) |
| **W2-9** | 負債解消 (KFP 2.16 互換 / mypy pre-existing 9 件 / parity test live 化) — 並行可 | §4.8 | — | 別 PR で吸収 |

各 step の詳細チェックリストは下記 §4.1〜§4.8 を参照。**Composer は Phase 7 = canonical で本実装** (`infra/terraform/modules/composer/` + 3 DAG + 関連 script は本 phase 配下にすべて存在。引き算で Phase 6 派生は別 phase 作業 — §4.7)。

---

### 4.1 Wave 2 実装済み項目

W2-1 / W2-2 / W2-3 / W2-5 / W2-6 / W2-7 の実装済み内容は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を正本とするため、ここでは重複記載しない。

残:
- [ ] Terraform outputs を `scripts.setup.deploy_all` の live overlay へ接続
- [ ] parity test を live 環境で実行し、閾値を確定
- [ ] `scripts.deploy.monitor` に vector_search smoke step を追加 — `run-all-core` に既存 smoke があるため優先度低
- [ ] `make composer-deploy-dags` が Phase 7 環境でも DAG deploy できることを確認 (§4.7)

### 4.6 互換レイヤ撤去 + canonical 化 (W2-8 = M6 達成)

Wave 1 で導入した backend 切替 env / BQ fallback / legacy alias を撤去し、Phase 7 の実装を 1 経路に収束させる:

- [ ] live で Vertex Vector Search / Feature Online Store / embed pipeline upsert の canonical 経路を 1 週間 dev で動かす — **dev PDCA は destroy-all で短命化する都合 1 週間 soak は不可**。代替として「`run-all-core` 完走 + `ndcg_at_10=1.0` を ack 条件にする」運用に短縮 (2026-05-02 達成)
- [ ] `BigQuerySemanticSearch` と `BigQueryFeatureFetcher` を削除し、対応 unit / integration test を Vertex canonical 前提へ更新する — **次 session の主作業**。touch 範囲 12 file (`app/services/adapters/bigquery_semantic_search.py`, `app/services/adapters/bigquery_feature_fetcher.py`, `app/services/adapters/bigquery_candidate_retriever.py` の選択分岐, `app/composition_root.py`, `app/container/search.py`, `app/services/protocols/semantic_search.py` の docstring, `app/settings/api.py`, `scripts/lib/config.py`, `infra/manifests/search-api/configmap.example.yaml`, `infra/manifests/search-api/deployment.yaml`, 関連 unit test, `app/services/adapters/__init__.py` re-export)
- [ ] `SEMANTIC_BACKEND` / `FEATURE_FETCHER_BACKEND` / related ConfigMap keys を削除し、search-api manifest を canonical 1 経路の設定だけに縮約する — 上記と同 PR
- [ ] embed pipeline の `enable_vector_search_upsert=true` + `vector_search_index_resource_name` を実 index に向けて daily run (Composer DAG `daily_feature_refresh` から submit、§4.7) — Composer 継承待ち (W2-4)。現状は `make deploy-all` の `backfill-vvs` step と manual smoke で実 upsert は確認済 (one-shot)
- [ ] 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) / [docs/03_実装カタログ.md](../architecture/03_実装カタログ.md) / [docs/05_運用.md](../runbook/05_運用.md) を canonical 実装 1 本に更新する — `04_検証.md` / `05_運用.md` は 2026-05-02 終端で `run-all-core` 完走と `SEARCH_RETRIES` 反映済。`01_仕様と設計.md` と `03_実装カタログ.md` は W2-8 削除と同期して更新する

### 4.7 Cloud Composer 本実装 (W2-4、Phase 7 = canonical / 引き算で Phase 6 派生)

**Phase 7 で Composer module / 3 DAG / make target / scripts を本実装する** (= 教材コード完成版の到達ゴールに必要な技術が Phase 7 に揃っている前提。引き算チェーン上の Phase 6 論理境界は別 phase 作業で派生させる)。

**Stage 1 (skeleton) 完了状態 (2026-05-02 終端)**:

- [x] `infra/terraform/modules/composer/` を新設 (main.tf / variables.tf / outputs.tf / versions.tf、`enable_composer=false` default で count=0 = no-op)
- [x] `infra/terraform/modules/iam/main.tf` に `sa-composer` SA + 4 role (`composer.worker` / `aiplatform.user` / `bigquery.{jobUser,dataViewer}` / `run.invoker`) + deployer SA に `composer.admin` 追加。`outputs.tf` の `service_accounts` map に `composer` entry 追加 (= 11 SA 体制)
- [x] `infra/terraform/environments/dev/main.tf` で `module "composer"` 配線 (depends_on: iam / data / vector_search / vertex)
- [x] `variables.tf` に `enable_composer` (default false) / `composer_environment_name` / `pipeline_template_gcs_path` 追加
- [x] `outputs.tf` に `composer_dag_bucket` / `composer_airflow_uri` / `composer_environment_name` 追加
- [x] `make tf-validate` PASS / `make check` 565 passed / workflow contract 8 passed / `make check-layers` PASS

**Stage 2 (3 DAG + deploy script + tests)** (本 PR で実施):

- [ ] `pipeline/dags/` 新設 (`__init__.py` / `_common.py` / `daily_feature_refresh.py` / `retrain_orchestration.py` / `monitoring_validation.py`)
- [ ] 各 DAG の責務:
  - `daily_feature_refresh` (schedule `0 16 * * *` = 01:00 JST): Dataform run + Feature View sync + (opt) VVS incremental backfill
  - `retrain_orchestration` (schedule `0 19 * * *` = 04:00 JST、本線 retrain): check_retrain → submit_train_pipeline (`scripts.ops.train_now` 経由で KFP 2.16 issue 回避) → wait_succeeded → promote_reranker (manual gate)
  - `monitoring_validation` (schedule `30 19 * * *`): run_feature_skew / run_model_output_drift (BigQueryInsertJobOperator) + check_slo_burn_rate
- [ ] `scripts/deploy/composer_deploy_dags.py` 新設 (terraform output `composer_dag_bucket` を読み、`pipeline/dags/*.py` を GCS に upload)
- [ ] `Makefile` に `composer-deploy-dags` / `ops-composer-trigger` / `ops-composer-list-runs` 追加
- [ ] `scripts/setup/deploy_all.py::_steps()` を 14 → 15 step 化 (`composer-deploy-dags` を `deploy-api` 直前に挿入、`enable_composer=false` 時は early-return)
- [ ] `TF_APPLY_STAGE1_TARGETS` に `module.composer` 追加
- [ ] `tests/unit/pipeline/dags/` 新設 (DagBag loader test / DAG 構造 pin / SQL path verify)
- [ ] `tests/unit/scripts/test_composer_deploy_dags.py` 新設 (terraform output mock + GCS upload mock)
- [ ] `scripts/ci/layers.py` の DIRECTORY_RULES に `pipeline/dags/` ルール追加 (airflow / google.cloud / scripts import 可、`app.*` 禁止)
- [ ] `pyproject.toml` の dev-dependencies に `apache-airflow >= 2.10, < 3` 追加

**Stage 3 (live verify)** (Stage 2 完了後):

**コスト見積もり (asia-northeast1、当日 destroy 前提)** — 詳細は [docs/runbook/05_運用.md §1.4-bis](../runbook/05_運用.md):

| シナリオ | コスト |
|---|---|
| Phase 7 full 学習 1 回 (3h 起動、即 destroy) | **~¥870-1,200/回** |
| 同日 2 回まわす | **~¥1,740-2,400/日** |
| 月 10 回 (週 2-3 回 verify) | **~¥8,700-12,000/月** |
| destroy 漏れ 24h 放置 | ~¥4,000-6,000 (Composer + GKE + VVS deployed index 等の合算) |

→ **当日 destroy 前提なら、判断材料は「許容時間内に収まるか」と「~¥870-1,200/回を学習投資として許容するか」**。Billing Budget Alert 日次 ¥3,000 推奨。

- [ ] `enable_composer=true` default flip
- [ ] 軽量 trigger 格下げ:
  - Cloud Scheduler `check-retrain-daily`: schedule `0 4 * * *` → `0 4 1 * *` (月 1 回 smoke)、description 更新
  - Cloud Function `pipeline_trigger` + Eventarc 2 本: ヘッダコメントに「smoke / 軽量代替経路として残置」追記
  - `/jobs/check-retrain` endpoint: docstring に「manual smoke / Composer DAG `check_retrain` task が呼ぶ用」追記
- [ ] live `make deploy-all` 完走確認 (Composer 環境作成 ~20 min 増加、合計 50-65 min)
- [ ] `make composer-deploy-dags` PASS (DAG GCS upload + Composer scheduler reparse)
- [ ] `make ops-composer-trigger DAG=retrain_orchestration` → Airflow UI で SUCCEEDED 確認
- [ ] `make run-all-core` 既存 PASS 維持 (`ndcg_at_10=1.0`)
- [ ] W2-8 統合 live re-verify (互換レイヤ削除 + Composer apply で `/search` canonical 経路 PASS)

**撤去対象が本線として再導入されていないこと** (CI 検証):

- [x] Vertex `PipelineJobSchedule` resource が残っていない — `grep -rn "google_vertex_ai_pipeline_job_schedule\|PipelineJobSchedule" infra/terraform/` で hit 無し (2026-05-02 確認)
- [ ] Cloud Scheduler `check-retrain-daily` が本線 retrain trigger になっていない — Stage 3 で月 1 回 smoke 専用に格下げ予定。リソース自体は `infra/terraform/modules/messaging/main.tf:103` で残置 (軽量代替用途)
- [ ] Eventarc `retrain-to-pipeline` が本線 trigger になっていない — Stage 3 で docstring 更新予定、`infra/terraform/modules/vertex/main.tf:158` で残置
- [ ] Cloud Function (Gen2) `pipeline-trigger` が本線 trigger になっていない — 同上、`infra/terraform/modules/vertex/main.tf:116` で残置
- [x] `/jobs/check-retrain` HTTP endpoint は API smoke / manual trigger 専用 — `app/api/routers/retrain_router.py:18` に残置、本線スケジューラからは独立した manual POST endpoint であることを code 確認

### 4.8 Wave 1 由来の負債解消 (W2-9、並行可)

Wave 2 本線と並行で別 PR にて吸収可:

- [ ] **KFP 2.16 互換 issue**: `pipeline.data_job.main` の `@dsl.pipeline` decorator が KFP 2.16 で TypeError を出す pre-existing 問題 (PR-3 の text wiring test で暫定対処)。根本 fix は KFP version pin or component annotation 修正 — text wiring test で暫定的に CI 通過中、live pipeline submit は別経路 (`scripts.ops.train_now`) で代替済のため緊急度は中
- [x] mypy pre-existing 9 件は解消済
- [x] `tests/integration/parity/` の live GCP 比較 test 雛形は追加済

---

## 5. Wave 3 — docs / reference architecture との整合 (確認のみ)

- [ ] 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) §「実案件想定の reference architecture」(Phase 5 docs を参照する旨) が最新であること — W2-8 削除と同期して再確認 (canonical 1 経路化後)
- [ ] コードに `Elasticsearch` / `synonym` / `query expansion` 等の固有名が混入していないことを `scripts/ci/layers.py` の禁止語リスト (or grep based check) で守る — 任意の追加チェック (現状コード grep では hit 無しを 2026-05-02 終端で確認)
- [x] [docs/05_運用.md](../runbook/05_運用.md) の「semantic 経路」「feature 取得経路」記述は 2026-05-02 終端更新 (`SEARCH_RETRIES` env table 追記)。残: [docs/03_実装カタログ.md](../architecture/03_実装カタログ.md) を Wave 1 / Wave 2 完了に追従して更新 — W2-8 削除と同期

---

## 6. リスクと回避

| 状態 | リスク | 回避 |
|---|---|---|
| ✅ 解消 | 大型 PR になりがち | 1 PR = 1 Port (PR-1 ～ PR-4) で 4 PR に分割。Wave 2 で互換レイヤ削除まで完了させる前提に修正 |
| ⚠ 要解消 | 互換レイヤを完成形と誤認する | Wave 1 の backend 切替・fallback は暫定。M6 の達成条件に **削除** を含め、教育コードとして 1 経路へ収束させる |
| ✅ 解消 | feature parity 6 ファイル更新漏れ | PR-2 / PR-4 ともに `FEATURE_COLS_RANKER` の 3 軸 (ctr / fav_rate / inquiry_rate) を merge する設計で、新規追加の 6 ファイル不変 (parity invariant test を破らない) |
| ✅ 解消 | Vertex Vector Search index の build 時間 | 2026-05-02 終端: `scripts/setup/backfill_vector_search_index.py` を `make deploy-all` 本線 step (`backfill-vvs`) に統合。daily incremental は Composer DAG 継承後 (W2-4) |
| ⏳ Wave 2 | Feature Online Store のコスト | `enable_feature_online_store` default=true (W2-2)、コスト管理は `make destroy-all` 運用に依存。app 層の互換レイヤは W2-8 で削除 |
| ✅ 解消 | Vertex Vector Search match endpoint の権限不足で 403 | `sa-api` の `roles/aiplatform.user` で VVS / FOS とも素通り。reranker SA も同 role 付与 (W2-3-b)。live で `ops-search` / `ops-vertex-vector-search-smoke` PASS |
| 🟡 部分立証 | BQ → VVS の embedding 不整合 | `backfill-vvs` 完走後に VVS smoke (5 neighbors) と BQ count とも non-zero を確認済。Cloud Logging での正式観測 + `tests/integration/parity/*` の live 実行は別 session |
| ⚠ 残存 | KFP 2.16 と既存 `data_job.main` の `@dsl.pipeline` validation error (HEAD でも再現) | PR-3 の wiring test を text-based に変更で暫定対処。live pipeline submit は `scripts.ops.train_now` 経路で代替済 (緊急度: 中)。根本 fix は §4.8 W2-9 で別 PR |

---

## 7. マイルストーン

| ID | フェーズ | 状態 | 完了内容 | 達成日 / 証跡 |
|---|---|---|---|---|
| M1 | ローカル | ✅ | PR-1 merge | 2026-05-01 — `SEMANTIC_BACKEND=vertex_vector_search` で adapter 切替動作、PR-1 17 tests PASS |
| M2 | ローカル | ✅ | PR-2 merge | 2026-05-01 — `FEATURE_FETCHER_BACKEND` group で adapter 切替、PR-2 18 tests PASS (Container 配線は M4 で完成) |
| M3 | ローカル | ✅ | PR-3 merge | 2026-05-01 — embed pipeline DAG に upsert component 追加、PR-3 17 tests PASS |
| M4 | ローカル | ✅ | PR-4 merge | 2026-05-01 — Container/SearchService/run_search 配線完了、`feature_fetcher=None` で挙動不変、PR-4 11 tests PASS |
| **M-Local** | **ローカル完結** | **✅** | **M1〜M4 全 merge** | **2026-05-01 — `make lint` / `make fmt-check` / 関連 mypy / pytest 63 passed**。**ただし教育コードとしては未完成で、Wave 2 の live 検証と互換レイヤ削除が残る** |
| M5 | GCP | ✅ | Wave 2 wiring + run-all-core 完走 | 2026-05-02 — live GCP で `/search` が Vertex Vector Search / Feature Online Store canonical 経路で 200。`make run-all-core` 完走、`ndcg_at_10=1.0`。残: W2-4 Composer Stage 2 / Stage 3 (3 DAG 本実装 + live verify) と live_gcp parity test の本実行 |
| M6 | GCP | ⏳ | 互換レイヤ撤去 (W2-8) | **次 session の主作業**: `BigQuerySemanticSearch` / `BigQueryFeatureFetcher` / `SEMANTIC_BACKEND` / `FEATURE_FETCHER_BACKEND` を削除し、本 phase docs/01 §4 表を canonical 実装 1 本へ更新。touch 範囲 12 file (§4.6 参照) |
| M7 | docs | 🟡 | Wave 3 確認 (一部進行中) | 2026-05-02 — `04_検証.md` / `05_運用.md` は run-all-core 完走と `SEARCH_RETRIES` 反映済 / `Elasticsearch` / `synonym` grep 0 件確認。残: `docs/01_仕様と設計.md` / `docs/03_実装カタログ.md` を W2-8 削除と同期して canonical 1 本に更新 |

---

## 8. 関連 docs

- 親リポ:
  - [README.md](../../../../README.md) §1 教材対象外 / §3 非負制約 / §4 学習運用
  - [CLAUDE.md](../../../CLAUDE.md) §「非負制約 (Phase 3/4/5/6/7 共通)」
  - [docs/01_仕様と設計.md](../../../../docs/architecture/01_仕様と設計.md) §「ハイブリッド検索の仕様と設計 (Phase 3-7 共通)」
- 本 phase:
  - [README.md](../README.md)
  - [CLAUDE.md](../CLAUDE.md)
  - [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) §「実案件想定の reference architecture」(Phase 5 を継承)
  - [docs/TASKS_ROADMAP.md](TASKS_ROADMAP.md) Port / Adapter / DI 大枠
  - [docs/decisions/](../decisions/README.md) 過去の制約決定 (ADR 0001〜0008)
- Phase 5 (継承元):
  - [5/study-hybrid-search-vertex/docs/01_仕様と設計.md](../../../../5/study-hybrid-search-vertex/docs/01_仕様と設計.md)
  - [5/study-hybrid-search-vertex/docs/02_移行ロードマップ.md](../../../../5/study-hybrid-search-vertex/docs/02_移行ロードマップ.md)
