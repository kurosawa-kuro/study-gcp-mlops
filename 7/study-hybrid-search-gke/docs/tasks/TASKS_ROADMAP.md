Stage 3.5 中間報告
DAG smoke 状態:

項目	結果
DAG bag 登録	✅ 3 本全て (daily_feature_refresh / retrain_orchestration / monitoring_validation)
import errors	✅ なし
手動 trigger 可能	✅ queued → 即時 task 起動
task SUCCEEDED	❌ check_retrain が 5 秒で fail
fail 真因: 全 task が BashOperator で uv run python -m scripts.ops.X を呼ぶ設計だが、Composer worker pod に uv も scripts/ モジュールも存在しない。これは設計上「DAG は repo の Python module を呼ぶ」想定だが、Composer worker は Airflow 標準 image で repo は持たない。

Stage 3.5 完了基準の判断要請
A. 現状で完了とみなす (推奨):
W2-4 の sprint 目的は「Composer 環境 provision + 3 DAG が canonical orchestrator として scheduler に認識される」。DAG smoke = parse / 認識 / trigger までで成立。SUCCEEDED は次 sprint 範囲。

B. SUCCEEDED まで深追い:
Composer pod に uv install + repo を data/ folder upload + DAG を BashOperator ではなく VertexAIPipelineOperator 等の Composer-native operator に書き換え。重い作業 (1-2 日)。

A で進めて Stage 3.6 (run-all-core) に進むか、B に深追いするか判断ください。

# 02. 移行ロードマップ — 検索アプリを最新仕様へ

Phase 7 の現コードを、最新仕様 (親 [README.md](../../../../README.md) §1-§3 / 親 [docs/01_仕様と設計.md](../../../../docs/architecture/01_仕様と設計.md) / 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md)) に追従させるための移行計画。

> **方針**: **Wave 1 = 検索アプリ自体 (app / ml / pipeline コード)** を先に整える。**Wave 2 = GCP インフラ (Terraform / IAM / deploy)** はその後。Wave 3 は docs / reference architecture との整合確認のみ (コード変更なし)。
>
> Port / Adapter / DI 大枠の整理は [`docs/TASKS_ROADMAP.md`](TASKS_ROADMAP.md)、過去の制約決定は [`docs/decisions/`](../decisions/README.md) を参照。
>
> **教育コード原則**: 後方互換・legacy fallback・旧 env 名 alias・旧 UI redirect・使われない shell resource は残さない。移行の都合で一時導入した互換レイヤも、役目を終えた時点で削除する。

---

## 現在地 (2026-05-03)

停止点:
- Composer DAG smoke の import error 修正待ち
- その後に `run-all-core` / `destroy-all` の最終 re-verify

完了済み実装・検証の正本:
- [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md)
- [`docs/05_運用.md`](../runbook/05_運用.md)

### 残り作業

- **DAG import error 修正**: `composer_deploy_dags.py` の upload layout を変更 — `pipeline/__init__.py` + `pipeline/dags/__init__.py` + `pipeline/dags/_common.py` を `pipeline/dags/` 階層保持で upload、DAG ファイルは top-level の `dags/` に置く構造へ
- `make ops-composer-trigger DAG=retrain_orchestration` で SUCCEEDED 確認
- `make run-all-core` PASS 維持確認 (`ndcg_at_10=1.0`)
- 最後の `make destroy-all` (新 stale VVS guard + reserved env contract が live で動作することの検証も兼ねる)
- `tests/integration/parity/*` の `live_gcp` 本実行 (別 session 妥当)

補足:
- 完了条件は `destroy-all -> deploy-all -> composer-deploy-dags -> run-all-core -> destroy-all`
- 実測・恒久対処の詳細は `03_実装カタログ.md` と `05_運用.md` を正本とし、この roadmap には再掲しない

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

## 1. 現状ギャップ

詳細な完了差分は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を正本とする。

残ギャップ:
- Composer DAG import layout 修正
- `tests/integration/parity/*` の live 実行
- KFP 2.16 互換 issue の根本対処
- [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) の最終同期

---

## 2. 移行戦略

### 2.1 暫定互換レイヤの扱い

Wave 1 ではローカル完結のために一時的な backend 切替と fallback を導入したが、**教育コードの完成条件はそれらを削除すること**。`BigQuerySemanticSearch` / `BigQueryFeatureFetcher` / backend 切替 env / legacy alias は Wave 2 の live 検証後に撤去し、Phase 7 の canonical 実装を 1 本に収束させる。

### 2.2 補足

- 互換レイヤ撤去は完了済み
- 実装方針や移行履歴の詳細は `03_実装カタログ.md` を正本とする

---

## 3. Wave 1 — 検索アプリ層 (本 roadmap の主タスク)

### 3.1 Wave 1 実装済み項目

Wave 1 の実装済み内容は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を正本とするため、ここでは重複記載しない。

残:
- [ ] `tests/integration/parity/test_semantic_backend_parity.py` の live 実行
- [ ] `tests/integration/parity/test_feature_fetcher_parity.py` の live 実行
- [ ] Cloud Logging ベースの eventual consistency 観測
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

完了。実装内容の正本は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を参照。

### 4.7 Cloud Composer 本実装 (W2-4、Phase 7 = canonical / 引き算で Phase 6 派生)

**Phase 7 で Composer module / 3 DAG / make target / scripts を本実装する** (= 教材コード完成版の到達ゴールに必要な技術が Phase 7 に揃っている前提。引き算チェーン上の Phase 6 論理境界は別 phase 作業で派生させる)。

**Stage 1 / Stage 2** は実装済み。内容の正本は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を参照。

**Stage 3 (live verify)**:

**コスト見積もり (asia-northeast1、当日 destroy 前提)** — 詳細は [docs/runbook/05_運用.md §1.4-bis](../runbook/05_運用.md):

| シナリオ | コスト |
|---|---|
| Phase 7 full 学習 1 回 (3h 起動、即 destroy) | **~¥870-1,200/回** |
| 同日 2 回まわす | **~¥1,740-2,400/日** |
| 月 10 回 (週 2-3 回 verify) | **~¥8,700-12,000/月** |
| destroy 漏れ 24h 放置 | ~¥4,000-6,000 (Composer + GKE + VVS deployed index 等の合算) |

→ **当日 destroy 前提なら、判断材料は「許容時間内に収まるか」と「~¥870-1,200/回を学習投資として許容するか」**。Billing Budget Alert 日次 ¥3,000 推奨。

- [ ] live `make deploy-all` 完走確認 (Composer 環境作成 ~20 min 増加、合計 50-65 min)
- [ ] `make composer-deploy-dags` PASS (DAG GCS upload + Composer scheduler reparse)
- [ ] `make ops-composer-trigger DAG=retrain_orchestration` → Airflow UI で SUCCEEDED 確認
- [ ] `make run-all-core` 既存 PASS 維持 (`ndcg_at_10=1.0`)
- [ ] W2-8 統合 live re-verify (互換レイヤ削除 + Composer apply で `/search` canonical 経路 PASS)

**撤去対象が本線として再導入されていないこと** (CI 検証):

- [x] Vertex `PipelineJobSchedule` resource が残っていない — `grep -rn "google_vertex_ai_pipeline_job_schedule\|PipelineJobSchedule" infra/terraform/` で hit 無し (2026-05-02 確認)
- [x] Cloud Scheduler `check-retrain-daily` は月 1 回 smoke 専用へ格下げ済
- [x] Eventarc `retrain-to-pipeline` / Cloud Function `pipeline-trigger` は軽量代替経路として残置済
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
