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

| Wave | フェーズ | 状態 | 内容 |
|---|---|---|---|
| **Wave 1** | ローカル完結 (検索アプリ層) | **✅ 完了 (M-Local 達成)** | PR-1 〜 PR-4 全 merge、`make lint` / `make fmt-check` / 関連 mypy / pytest 63 passed || **Wave 2** | **GCP インフラ層 (= クラウド側の主作業計画)** | 🟢 wiring + run-all-core 完走 (W2-8 / W2-4 残) | §4 が母艦。**W2-1 / W2-2 / W2-3 / W2-5 / W2-6 / W2-7 の live wiring は成立 + `make run-all-core` 完走 (`ndcg_at_10=1.0`)**。**ops-search 透過 retry / canonical ConfigMap auto-flip / `ops-train-wait` 実装済 / W2-4 Composer module skeleton 着地済 (`enable_composer=false` default)**。未完了は **W2-8 互換レイヤ削除 (Stage 別 PR 中) / W2-4 Composer 3 DAG 本実装 + live verify / live_gcp parity 本実行 / 最終 destroy-all** |
| Wave 3 | docs / reference architecture 整合 | 🟡 一部進行中 | `04_検証.md` / `05_運用.md` は 2026-05-02 終端で更新済 (run-all-core 完走 / SEARCH_RETRIES 反映)。残: `01_仕様と設計.md` / `03_実装カタログ.md` を W2-8 削除と同期 |

## 現在地サマリ (2026-05-02)

### 残り作業

- 最後の `destroy-all` (PDCA cycle clean state リセット)
  - `destroy-all -> deploy-all -> run-all-core` までは PASS、最後の `destroy-all` のみ user 判断待ち (cluster は残置中)
- `W2-8` 互換レイヤ撤去
  - `SEMANTIC_BACKEND`
  - `FEATURE_FETCHER_BACKEND`
  - `BigQuerySemanticSearch`
  - `BigQueryFeatureFetcher`
- W2-4 Composer 本実装 (Phase 7 = canonical 起点。Stage 1 skeleton 着地済、Stage 2 で 3 DAG 本実装、Stage 3 で live verify)
- `tests/e2e/` / `live_gcp` parity の本実行

### 現在の状態 (2026-05-02 終端)

- **`run-all-core` 完走 ✅** (exit 0)
  - `ops-livez` / `ops-search-components` (`lexical=1 semantic=3 rerank=5`) / `ops-vertex-vector-search-smoke` / `ops-vertex-feature-group` / `ops-search` / `ops-feedback` / `ops-ranking` / `ops-train-now` + `ops-train-wait` / `ops-label-seed` / `ops-daily` / `ops-accuracy-report` (`ndcg_at_10=1.0 hit_rate=1.0 mrr=1.0`) が全 PASS
- **`/search` の read timeout は解消** — `scripts/ops/search.py` に `SEARCH_RETRIES` (default 3) / `SEARCH_RETRY_SLEEP` (default 2.0s) の transient リトライを実装。今回の run-all-core 実走では retry を一度も発火させずに 1 発 PASS。リトライは将来の cold-start / rolling restart 中の偶発 timeout 用 safety net として残置
- `deploy-all` は完走するが、managed service の長待機が大きい
  - VVS deployed index attach は 2026-05-02 実測で **26m21s**
  - 待機そのものは bug ではないが、PDCA 速度を大きく悪化させる

### 今回の主要な失敗事例

- `deploy-all` 本線に `sync-meili` が入っておらず、完走後でも `lexical=0`
- `deploy-all` 本線に `backfill-vvs` が入っておらず、完走後でも `0 neighbors`
- `trigger-fv-sync` が seed 前提を満たさず、Feature View fetch が 404
- `property_features_online_latest` を同一 apply で早く作りすぎて 404
- `module.kserve` / `helm_release` が GKE ready 前に走って timeout
- stale VVS deployed index が残り、再作成で 400 conflict
- `run-all-core` が部分的に通っていても、最後に `/search` timeout で全体 FAIL

### 今回の反省

- 最大の失敗要因は個別バグだけではなく、**不必要なブロッキング**だった
- 早期に出ていた停滞シグナルや error を AI 側が即切らず、放置する時間が長すぎた
- ユーザーが進捗確認を何度も入れて初めて問題が顕在化する悪循環を作った
- 部分成功 (`ops-*` 単体 PASS) を、ユーザー価値のある完了 (`full PDCA PASS`) と混同しかけた
- 今後の基準は以下に固定する
  - 30 秒超の待機は「現在地 / 待機理由 / 次の分岐」を即報告
  - 3 分超の待機は異常候補として切り分けに移る
  - 長待機中は docs 更新、contract test 追加、代替検証を並行実行
  - `destroy-all -> deploy-all -> run-all-core -> destroy-all` が通るまで完了扱いしない

### 進捗ログ (2026-05-02)

「何も進んでいないのでは」という不安を避けるため、Wave 2 live 検証で実際に通した項目と、まだ残る項目を分離して記録する。

**この時点で実測 PASS 済み**

- 8 件バグ修正 (live 検証中に発覚) は **コード上で全て done**:
  - **#4 FOS Optimized lifecycle.ignore_changes** — `infra/terraform/modules/vertex/main.tf:289-294` に `ignore_changes = [optimized, dedicated_serving_endpoint, labels]` を追加。Update API 未サポートの 400 を回避
  - **#5+#9 deploy-all step list 拡張** — `scripts/setup/deploy_all.py::_steps()` に `seed-test` (step 8) と `trigger-fv-sync` (step 11) を追加 + 新 helper `scripts/infra/feature_view_sync.py`
  - **#6 ConfigMap が Terraform output から VVS/FOS 値を自動注入** — `scripts/deploy/configmap_overlay.py::_terraform_output_map()` + `scripts/lib/config.py::generate_configmap_data` 拡張
  - **#7 provider を kubeconfig-based に切替** — `infra/terraform/environments/dev/provider.tf` から `data.google_container_cluster` 直参照を撤去、`config_path` / `config_context` 経由に固定。`var.k8s_use_data_source` は廃止 (variables.tf から削除、recover_wif.py の placeholder mode も撤去)
  - **#8 deploy_all 失敗時 last-line summary** — `scripts/setup/deploy_all.py::main()` の except 句で `==> deploy-all FAILED at step N (name)` を stdout 末尾に出力 (pipe で exit code が消える wrapper invocation 対策)
  - **#10 feature_group.py 404 診断強化** — `scripts/ops/vertex/feature_group.py::_emit_404_diagnostics()` で recent FeatureViewSyncs / BQ source row count / next_action hint を表示
  - **#11 enable_vector_search / enable_feature_online_store default=true** — `infra/terraform/environments/dev/variables.tf` で両 var の default を `true` に。`TF_VAR_enable_*=true` の手動 export 不要
- **9 件目 (run-all-core 中断 root cause) も解消済み** (2026-05-02 終端):
  - **`scripts/ops/search.py` に transient リトライを追加** — `SEARCH_RETRIES` (default 3) / `SEARCH_RETRY_SLEEP` (default 2.0s)。`TimeoutError` / `URLError` / `OSError` のみ retry、それ以外は即 fail。`fail()` の出力先 (stderr) に対応した unit test 4 件 (`tests/unit/scripts/test_vertex_ops_scripts.py::test_ops_search_*`) も同 PR に同梱
  - **`make run-all-core` を retry 反映後に live 再走 → 完走 (exit 0)** — `ops-search` 1 発 PASS (retry 未発火)、`ops-accuracy-report` で `ndcg_at_10=1.0 hit_rate=1.0 mrr=1.0`
- local boot contract:
  - Docker build 成功
  - import smoke 成功
  - `ENABLE_SEARCH=false` で ADC なし `/livez` 200
- GCP canonical path:
  - `make ops-livez`
  - `make ops-search-components` (`lexical=1 semantic=3 rerank=5`)
  - `make ops-vertex-vector-search-smoke`
  - `uv run python -m scripts.infra.feature_view_sync`
  - `make ops-vertex-feature-group`
  - `make ops-feedback`
  - `make ops-ranking`
  - `make ops-accuracy-report` (`ndcg_at_10=1.0`)
  - `make ops-train-now` + `make ops-train-wait`
- workflow contract 強化:
  - ConfigMap overlay が Terraform outputs から VVS/FOS 値を注入
  - live overlay 時に `semantic_backend=vertex_vector_search` / `feature_fetcher_backend=online_store` へ auto-flip
  - `run-all-core` に `ops-vertex-vector-search-smoke` / `ops-vertex-feature-group` / `ops-train-wait` を組み込み
  - opt-in live acceptance gate に `feedback / ranking / accuracy / canonical ConfigMap` を追加
- destroy-all 再現性修正:
  - `Gateway` / `ServiceNetworkEndpointGroup` finalizer 詰まりを実害として確認し、回避手順を反映
  - `property_features_online_latest` の `deletion_protection` 漏れを修正
  - `tests/integration/infra/test_destroy_all_table_parity.py` を更新して再発防止
- docs 同期:
  - `TASKS.md`
  - `03_実装カタログ.md`
  - `04_検証.md`
  - `05_運用.md`

**full PDCA 再検証 (2026-05-02 終端)**

- `destroy-all → deploy-all → run-all-core` まで PASS。最後の `destroy-all` は user 判断待ちで cluster 残置中
- `deploy-all` の staged apply 化により、前回の blocker だった `property_features_online_latest` 404 / `module.kserve` / `helm_release` の GKE ready race は解消済み
- VVS deployed index attach は実測 **26m21s** (待機そのものは bug ではない)
- 旧 root cause だった「`deploy-all` 本線に `backfill_vector_search_index --apply` と `sync-meili` が無い」は修正済 (workflow contract は `seed-test -> sync-meili -> backfill-vvs -> trigger-fv-sync`)
- `make run-all-core` 完走時の実測:
  - `ops-livez` / `ops-search` / `ops-search-components` (`lexical=1 semantic=3 rerank=5`) / `ops-vertex-vector-search-smoke` / `ops-vertex-feature-group` / `ops-feedback` / `ops-ranking` / `ops-train-now` + `ops-train-wait` / `ops-label-seed` / `ops-daily` / `ops-accuracy-report` (`ndcg_at_10=1.0 hit_rate=1.0 mrr=1.0`) が全 PASS

**まだ未完了**

- **W2-8 互換レイヤ削除** (= 教育コード完成条件、次の主作業)
  - `SEMANTIC_BACKEND`
  - `FEATURE_FETCHER_BACKEND`
  - `BigQuerySemanticSearch`
  - `BigQueryFeatureFetcher`
  - manifest / docs 上の暫定切替 vehicle
- **W2-4 Composer 本実装** (Phase 7 = canonical 起点、§4.7 の Stage 2 / Stage 3)
  - Stage 1 skeleton 着地済 (module / IAM / dev wiring、`enable_composer=false` default)
  - Stage 2 (3 DAG + deploy script + Make + 15 step + tests) は本 PR 中
  - Stage 3 (`enable_composer=true` flip + 軽量 trigger 格下げ + live verify)
- `tests/integration/parity/*` の `live_gcp` 本実行
- 最後の `destroy-all` (PDCA cycle clean リセット、user 判断)

要点:

- 「主要な live wiring が動くか」は確認済み
- 「PDCA (`destroy-all → deploy-all → run-all-core`) を 1 発で完走できるか」も完走済み (最後の `destroy-all` のみ user 判断待ち)
- 「暫定互換レイヤをコードごと消す」が次の主作業として残っている

**Wave 1 の位置付け**:

- Wave 1 は **最終形ではなく暫定配線**。ローカル完結で adapter / Terraform / script を先に揃えただけで、教育コードとしての完成条件は **互換レイヤ削除後** とする
- 実 GCP 通信を伴う検証は Wave 2 で provision 後にまとめて smoke (2026-05-02 終端: `make run-all-core` 完走 / `ndcg_at_10=1.0` で立証済)
- 受け入れ条件のローカル部分は satisfied、GCP smoke も完走済。残るのは **互換レイヤ撤去 (W2-8)** のみで、それまでは **教育コードとしては未完成**

**63 unit tests 内訳** (`pytest tests/unit/app/test_*feature_fetcher* tests/unit/app/test_*semantic* tests/unit/app/test_*search_builder* tests/unit/app/test_*run_search_feature_fetcher* tests/unit/pipeline/test_vector_search* tests/unit/pipeline/test_data_job_dag*`):

- PR-1 (SemanticSearch / Vertex Vector Search): 17 tests
- PR-2 (FeatureFetcher / FOS): 18 tests
- PR-3 (VectorSearchWriter / pipeline): 17 tests
- PR-4 (Container 配線 + ranking.py merge): 11 tests

**Wave 2 で確認済みの補足**:
- `infra/manifests/kserve/reranker.yaml` の env vehicle 追加は **不要**。旧案は廃止し、search-api ConfigMap 経由へ一本化済。PR-4 docstring の予告は close
- `scripts/ci/sync_configmap.py` は **追従済**。`configmap.example.yaml` の Wave 2 キー (`semantic_backend` / `vertex_vector_search_*` / `feature_fetcher_backend` / `vertex_feature_*`) を generator が再現する
- `scripts/lib/config.py` / `scripts.deploy.configmap_overlay` は **live canonical flip 対応済**。Terraform outputs から VVS/FOS 値が入ると `semantic_backend=vertex_vector_search` / `feature_fetcher_backend=online_store` に自動で切り替わる
- `tests/integration/parity/test_semantic_backend_parity.py` / `test_feature_fetcher_parity.py` の **live GCP 雛形は追加済**。local / CI では `live_gcp` marker で skip、実行は Wave 2 live smoke 時に行う
- `W2-9` の **mypy pre-existing 9 件** (`search_service.py` / `lexical_search.py` / `ops_router.py` / `tests/conftest.py`) は解消済。KFP 2.16 互換 issue のみ継続

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

### 3.1 PR-1: `SemanticSearch` Port — Vertex Vector Search adapter [ローカル完結 ✓ / **実装済 ✅ 2026-05-01**]

**目的**: ME5 で encode したクエリベクトルを Vertex AI Vector Search の match endpoint に投げ、候補 (property_id + score) を返す経路を Port/Adapter で追加。BQ adapter は据え置き。**コードと unit/integration test までローカル完結。live GCP smoke は Wave 2。**

**実装結果 (2026-05-01)**:

- `app/services/adapters/vertex_vector_search_semantic_search.py` 新規 — `endpoint_factory` 注入 seam で SDK 未 import 完結
- `app/services/adapters/__init__.py` に export 追加
- `app/settings/api.py` に `semantic_backend: Literal["bq", "vertex_vector_search"] = "bq"` + `vertex_vector_search_index_endpoint_id` / `_deployed_index_id` フィールド追加
- `app/container/search.py` に `_resolve_semantic_search()` 追加 + `build_candidate_retriever` で wire
- `tests/unit/app/test_vertex_vector_search_semantic_search.py` 11 tests + `test_search_builder_semantic_backend.py` 6 tests = **17 tests PASS**
- mypy / ruff / format clean (PR-1 関連ファイル単体)
- 既存 `tests/_fakes/in_memory_semantic_search.py` を再利用 (新規 fake 不要だった)

**実装上の plan からの乖離**:

- 計画では `app/services/noop_adapters/in_memory_semantic_search.py` を新規追加予定 → 既存 `tests/_fakes/in_memory_semantic_search.py` で充足のため新規追加せず
- 計画の `tests/integration/parity/test_semantic_backend_parity.py` (live 比較) は Wave 2 用なので未追加
- 計画の `scripts/ci/layers.py` 更新: 既存 RULES が directory-level で吸収するため明示的更新不要だった
- `env/.env.example` ファイルは存在しないため未追加 (`env/config/setting.yaml` 流儀に合わせる)

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 新規 | `app/services/adapters/vertex_vector_search_semantic_search.py` | `aiplatform.MatchingEngineIndexEndpoint.find_neighbors()` を叩く adapter |
| 削除予定 | `app/services/adapters/bigquery_semantic_search.py` | Wave 1 暫定 fallback。Phase 7 canonical 化後に撤去 |
| 維持 | `app/services/protocols/semantic_search.py` | Port 定義は不変 (interface 同形なら既存で吸収) |
| 編集 | `app/composition_root.py` (or `app/container/search.py`) | `SEMANTIC_BACKEND` 環境変数で adapter 注入分岐 |
| 編集 | `app/settings/settings.py` | `semantic_backend` を暫定導入。Wave 2 の live 検証後に削除対象 |
| 新規 | `app/services/noop_adapters/in_memory_semantic_search.py` | テスト / ローカル開発用 fake (任意の固定 candidate を返す) |
| 新規 | `tests/unit/services/test_vertex_vector_search_semantic_search.py` | adapter 単体 (Vertex SDK は mock) |
| 新規 | `tests/integration/parity/test_semantic_backend_parity.py` | 同一クエリで BQ adapter と VVS adapter の上位 K が極端にズレないことを検証 (許容差は文書化) |
| 編集 | `scripts/ci/layers.py` の RULES | 新 adapter のレイヤ境界を追加 |

**設計メモ**:

- Vertex Vector Search の `find_neighbors` は `(neighbor_id, distance)` を返す。Port が要求する `SemanticResult(property_id, score, rank)` に合わせて変換する mapper をこの adapter 内に持つ
- `embedding_dim` は 768 (`ml/common/config/embedding.py`) で固定、index 作成時とランタイムで一致を保証
- 失敗時に旧 backend へ逃がさない。live 検証完了後は backend 切替自体を削除する
- 認証は ADC (Cloud Run / GKE の Workload Identity 経由)、ローカルは `gcloud auth application-default login`

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` (ruff format) PASS
- [x] PR-1 関連ファイル単体 mypy clean
- [x] PR-1 関連 17 tests PASS
- [x] in-memory fake 経由で `/search` adapter selection が分岐 (composition wiring test)
- [x] mock で Vertex SDK call (`find_neighbors`) を stub した unit test PASS
- [x] 既存 `tests/unit/app/test_api_contract_template.py` 不変
- [x] ~~`SEMANTIC_BACKEND=vertex_vector_search` を `env/.env.example` に追記~~ N/A (該当ファイル無し / `env/config/setting.yaml` 流儀)
- [x] `make check-layers` PASS (2026-05-02 終端実測 `check-layers: OK (51 files clean)`)

GCP smoke (Wave 2 で実施):
- [x] live `MatchingEngineIndexEndpoint.find_neighbors` 経由で `/search` 200 (run-all-core の `ops-search` PASS)
- [ ] `tests/integration/parity/test_semantic_backend_parity.py` の live 比較 PASS — 別 session で `LIVE_GCP_ME5_QUERY_VECTOR` を投入して実行

---

### 3.2 PR-2: `FeatureFetcher` Port — Feature Online Store adapter [ローカル完結 ✓ / **実装済 ✅ 2026-05-01**]

**目的**: rerank 入力 feature を Feature Online Store から取得する経路を Port/Adapter として用意。training-serving skew 防止 (Phase 5 必須要素を Phase 7 でも維持)。

**実装結果 (2026-05-01)**:

- `app/services/protocols/feature_fetcher.py` 新規 — Port + `FeatureRow` value object (`ctr` / `fav_rate` / `inquiry_rate` の 3 軸、`property_features_daily` の動的 feature と一致)
- `app/services/adapters/bigquery_feature_fetcher.py` 新規 — `property_features_daily` の latest event_date scan
- `app/services/adapters/feature_online_store_fetcher.py` 新規 — Vertex AI v1beta1 SDK lazy import + `endpoint_resolver` / `client_factory` 注入 seam
- `tests/_fakes/in_memory_feature_fetcher.py` 新規 — call 記録機能付き
- `app/settings/api.py` に `feature_fetcher_backend` + `vertex_feature_online_store_id` / `vertex_feature_view_id` / `vertex_feature_online_store_endpoint` 追加
- `app/container/search.py` に `resolve_feature_fetcher()` 追加 (public method、PR-4 が Container 配線で消費)
- `tests/unit/app/test_feature_fetcher_adapters.py` 11 tests + `test_feature_fetcher_wiring.py` 7 tests = **18 tests PASS**

**実装上の plan からの乖離**:

- 計画では PR-2 で `app/services/ranking.py` を改修して `FeatureFetcher` を直接呼ぶ予定だった → アーキテクチャ調査の結果、ranking.py からは `candidate.property_features` を読むだけで feature 取得は `BigQueryCandidateRetriever._enrich_from_bq` で完了している判明。**FeatureFetcher の Container 配線と consumption は PR-4 にまとめて実施**
- 計画の `tests/integration/parity/test_feature_fetcher_parity.py` (BQ vs FOS の値比較) は live GCP が必要なため Wave 2 用に skip
- PR-2 merge 段階では Container に未配線だったが、教育コードの完成条件は **未配線維持ではなく旧 BQ 経路の撤去** とする

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 新規 | `app/services/protocols/feature_fetcher.py` | `class FeatureFetcher(Protocol): def fetch(self, property_ids: list[str]) -> dict[str, FeatureRow]` |
| 新規 | `app/services/adapters/feature_online_store_fetcher.py` | Vertex AI SDK `FeatureOnlineStoreServiceClient.fetch_feature_values` |
| 削除予定 | `app/services/adapters/bigquery_feature_fetcher.py` | Wave 1 暫定 fallback。Phase 7 canonical 化後に撤去 |
| 新規 | `app/services/noop_adapters/in_memory_feature_fetcher.py` | fake (固定 feature を返す) |
| 編集 | `app/services/ranking.py` | feature 取得を直書きから `FeatureFetcher` Port 経由に変更 |
| 編集 | `app/composition_root.py` | `FEATURE_FETCHER_BACKEND` による暫定切替を導入。Wave 2 後に削除対象 |
| 編集 | `app/settings/settings.py` | `feature_fetcher_backend` を暫定導入。Wave 2 の live 検証後に削除対象 |
| 新規 | `tests/unit/services/test_feature_online_store_fetcher.py` | adapter 単体 |
| 新規 | `tests/integration/parity/test_feature_fetcher_parity.py` | bq fetcher と online store fetcher の取得値が一致 (training-serving skew チェック) |

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` PASS
- [x] PR-2 関連ファイル単体 mypy clean
- [x] PR-2 関連 18 tests PASS
- [x] in-memory fake fetcher が `FeatureFetcher` Port を充足することを test で確認
- [x] feature parity invariant 6 ファイル ([`pipeline/data_job/dataform/features/property_features_daily.sqlx`](../pipeline/data_job/dataform/features/property_features_daily.sqlx) etc.) は不変
- [x] `make check-layers` PASS (2026-05-02 終端実測 `check-layers: OK (51 files clean)`)

GCP smoke (Wave 2 で実施):
- [x] live `FeatureOnlineStoreServiceClient.fetch_feature_values` 経由で ranking 動作 (run-all-core の `ops-vertex-feature-group` で 7 features 取得 + `ops-ranking` で `final_rank/score/me5_score` 整合)
- [ ] `tests/integration/parity/test_feature_fetcher_parity.py` の live skew check PASS — 別 session で `VERTEX_FEATURE_ONLINE_STORE_ID` 投入して実行

---

### 3.3 PR-3: `VectorSearchWriter` Port — embed pipeline の二重書き [ローカル完結 ✓ / **実装済 ✅ 2026-05-01**]

**目的**: `embed_pipeline` が BQ embedding テーブルを書いた後、同じ embedding を Vertex Vector Search index に upsert する経路を追加。BQ は正本、Vertex Vector Search は serving index。

**実装結果 (2026-05-01)**:

- `pipeline/data_job/ports/vector_search_writer.py` 新規 — `VectorSearchWriter` Port + `EmbeddingDatapoint` value object
- `pipeline/data_job/adapters/vertex_vector_search_writer.py` 新規 — `MatchingEngineIndex.upsert_datapoints` lazy import + chunking (default 500/batch)
- `pipeline/data_job/adapters/in_memory_vector_search_writer.py` 新規 — idempotent in-memory writer + call recorder
- `pipeline/data_job/components/upsert_vector_search.py` 新規 — KFP component (manifest emit 型、`write_embeddings` と同パターン)
- `pipeline/data_job/main.py` 編集 — DAG に component 組み込み + `enable_vector_search_upsert` / `vector_search_index_resource_name` / `vector_search_upsert_batch_size` parameters 追加
- `tests/unit/pipeline/test_vector_search_writer.py` 12 tests + `test_data_job_dag_wiring.py` 5 tests = **17 tests PASS**

**実装上の plan からの乖離**:

- 計画では `dsl.If(enable_vector_search_upsert == True, ...)` で DAG 内 conditional 配置 → KFP 2.16 で `dsl.If` の version 互換性が fragile だったため、**「常に component を含める + runner 側 manifest を見て no-op」方針に変更**。`vector_search_index_resource_name == ""` で gate
- 計画の wiring test (`from pipeline.data_job import main` で signature 確認) が KFP 2.16 の **pre-existing import 失敗** で動かないことが判明 (HEAD でも再現)。**text-based 静的検証** (main.py を文字列として grep) に変更、テスト docstring に理由明記
- 計画の `ml/data/loaders/vector_search_upserter.py` は不要だった (adapter 内で完結)
- 初回 backfill `scripts/setup/backfill_vector_search_index.py` は予定通り Wave 2 へ

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 新規 | `pipeline/data_job/ports/vector_search_writer.py` | Port: `def upsert(rows: list[EmbeddingRow]) -> None` |
| 新規 | `pipeline/data_job/adapters/vertex_vector_search_writer.py` | `aiplatform.MatchingEngineIndex.upsert_datapoints` を呼ぶ adapter |
| 新規 | `pipeline/data_job/adapters/in_memory_vector_search_writer.py` | local fake |
| 編集 | `pipeline/data_job/components/` 内の embed コンポーネント | BQ MERGE の後段に upsert step を追加 (失敗しても BQ 側を巻き戻さない、観測可能性を持たせる) |
| 編集 | `pipeline/data_job/main.py` | DAG の wiring に upsert step を組み込み、`ENABLE_VECTOR_SEARCH_UPSERT` flag で skip 可能 |
| 新規 | `ml/data/loaders/vector_search_upserter.py` (任意) | low-level クライアント wrapper を ml 共通層に置く |
| 新規 | `tests/unit/pipeline/test_vector_search_writer.py` | fake で upsert が呼ばれることを検証 |

**設計メモ**:

- BQ MERGE と Vertex Vector Search upsert は **別トランザクション**。一方が失敗しても他方は完了する (eventual consistency 設計、観測可能性は Cloud Logging の構造化ログで担保)
- Vertex Vector Search index の build / refresh は本番では batch update を推奨。streaming update は cost が大きい
- 初回 backfill は別スクリプト (`scripts/setup/backfill_vector_search_index.py`) を Wave 2 で追加 — Wave 1 では DAG への組み込みのみ

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` PASS
- [x] PR-3 関連ファイル単体 mypy clean
- [x] PR-3 関連 17 tests PASS
- [x] `vector_search_index_resource_name=""` で no-op gate されることを test で確認
- [x] mock で `MatchingEngineIndex.upsert_datapoints` を stub した unit test PASS
- [x] DAG signature の暫定 gate (`enable_vector_search_upsert=False` 等) を text 検証
- [ ] `pipeline/data_job/main.py` を fake で完走 — KFP 2.16 import 不可のため **deferred**: text wiring test で代替 (上記乖離参照、根本対処は下記項目)

GCP smoke (Wave 2 で実施):
- [x] live `MatchingEngineIndex.upsert_datapoints` で実 index に書き込み (deploy-all step `backfill-vvs` = `scripts.setup.backfill_vector_search_index --apply` が live で完走、後続 `ops-vertex-vector-search-smoke` が 5 neighbors 返却で立証)
- [ ] BQ MERGE と VVS upsert が同一 run で eventual に整合 (Cloud Logging 観測) — 部分立証のみ (backfill 後に VVS smoke / BQ count とも non-zero)。Cloud Logging の正式観測は別 session
- [ ] KFP 2.16 import 互換 issue の根本対処 (別 issue 化推奨、PR-3 の text test はあくまで暫定)

---

### 3.4 PR-4: Feature Online Store 統合 (Phase 7 固有) [ローカル完結 ✓ / **実装済 ✅ 2026-05-01** — manifest apply のみ Wave 2]

**目的**: search-api が rerank 直前に Feature Online Store から feature を引く経路を追加し、旧 BQ enrich 依存を撤去する準備を整える。Wave 1 は live 前提を外した実装まで、完成条件は Wave 2 後の旧経路削除。

**実装結果 (2026-05-01)**:

- `app/services/ranking.py` 編集 — `_augment_with_fresh_features(candidates, fetcher)` ヘルパ追加 + `run_search` に `feature_fetcher: FeatureFetcher | None = None` パラメータ追加。fetch 失敗時は `logger.exception` + BQ-enriched 値で rerank 続行 (503 にしない)
- `app/services/search_service.py` 編集 — `__init__` で `feature_fetcher` 受取 → `run_search` に pass-through
- `app/composition_root.py` 編集 — `Container.feature_fetcher: FeatureFetcher | None` field 追加 + `ContainerBuilder.build` で `SearchBuilder.resolve_feature_fetcher()` の戻り値を SearchService に注入
- `tests/conftest.py` 編集 — `fake_container_factory` の defaults に `feature_fetcher: None` 追加 + SearchService 構築で渡す
- `tests/unit/app/test_run_search_feature_fetcher.py` 新規 — **11 tests PASS** (helper unit / run_search integration / Container wiring / signature 確認)

**実装上の plan からの乖離 (=> 設計改善)**:

- 計画では `app/services/adapters/kserve_reranker.py` を編集して predict 前に FeatureFetcher を呼ぶ予定 → アーキテクチャ調査で `KServeReranker.predict(instances)` は **既に build 済み feature 行列**を受け取る設計と判明。FOS merge は **特徴 fetch のレイヤ (= ranking.py の `_build_feature_matrix` 直前)** で行う方が責務分担として正しい。**`KServeReranker` は完全に touch せず**、ranking.py / SearchService / Container の 3 層で merge を完成
- 計画段階の旧 env 案は廃止 → PR-2 で導入した `FEATURE_FETCHER_BACKEND=online_store` + `vertex_feature_online_store_*` group で統一 (重複なし)
- 計画の `infra/manifests/kserve/reranker.yaml` env vehicle 追加は **Wave 2 と一緒に扱う方針**に変更 (manifest apply タイミングと一致させる方が安全)
- 計画の `tests/integration/test_kserve_reranker_with_online_store.py` (live KServe pod 検証) は Wave 2 用なので未追加 (代わりに run_search レベルの integration test で merge 経路を確認)

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 編集 | `app/services/adapters/kserve_reranker.py` | predict 前に `FeatureFetcher` を呼ぶ (Wave 1 では `FEATURE_FETCHER_BACKEND=online_store` group で暫定制御) |
| 編集 | `app/composition_root.py` | KServe reranker に対して FeatureOnlineStoreFetcher を注入する分岐 |
| 編集 | `app/settings/settings.py` | `kserve_feature_online_url: str | None = None` を追加 |
| 編集 | `infra/manifests/kserve/reranker.yaml` (Wave 2 寄りだが env だけ Wave 1 で追加可) | env 変数の vehicle を用意 |
| 新規 | `tests/integration/test_kserve_reranker_with_online_store.py` | 暫定制御あり / なしそれぞれで分岐確認 |

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` PASS
- [x] PR-4 関連ファイル単体 mypy clean (search_service.py の pre-existing 負債は別件)
- [x] PR-4 関連 11 tests PASS
- [x] default (`feature_fetcher=None`) で挙動変わらず (test で `fetcher.calls == []` を確認)
- [x] 設定時のみ FOS の fetch 経路に分岐 (test で `fetcher.calls == [["p001"]]` + matrix の 4/5/6 列が FOS-fresh 値)
- [x] FOS が落ちても `/search` は 503 にならず BQ-enriched 値で続行 (test で確認)
- [x] ~~`infra/manifests/kserve/reranker.yaml` env vehicle 追加~~ N/A — search-api ConfigMap 経由へ一本化済 (2026-05-02 時点で旧案廃止、Wave 2 補足参照)

GCP smoke (Wave 2 で実施):
- [x] live search-api pod に env 注入 → 実 Feature Online Store fetch 経路で `/search` 200 (live overlay で `feature_fetcher_backend=online_store` auto-flip 済、run-all-core の `ops-search` PASS)
- [x] env 未設定で従来挙動 (`scripts/lib/config.py` の strangler default `feature_fetcher_backend="bq"`、cluster apply 前のローカル overlay は default のまま落ちることを test で確認済)

---

### 3.5 全 PR 共通: composition root + settings + env 取り扱い (Wave 1 実装後)

| 環境変数 | 値域 | default | 影響 | 実装 PR |
|---|---|---|---|---|
| `SEMANTIC_BACKEND` | `bq` / `vertex_vector_search` | `bq` | semantic 検索 adapter 切替 | PR-1 ✅ |
| `VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID` | string | `""` | VVS adapter が参照する Index Endpoint ID (Wave 2 で provision) | PR-1 ✅ |
| `VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID` | string | `""` | VVS adapter の `deployed_index_id` (Wave 2 で provision) | PR-1 ✅ |
| `FEATURE_FETCHER_BACKEND` | `bq` / `online_store` | `bq` | rerank 用 feature 取得 adapter 切替 | PR-2 ✅ |
| `VERTEX_FEATURE_ONLINE_STORE_ID` | string | `""` | FOS adapter が参照する store ID (Wave 2 で provision) | PR-2 ✅ |
| `VERTEX_FEATURE_VIEW_ID` | string | `""` | FOS adapter が参照する view ID (Wave 2 で provision) | PR-2 ✅ |
| `VERTEX_FEATURE_ONLINE_STORE_ENDPOINT` | string | `""` | FOS regional public endpoint (Wave 2 で Admin API 経由 lookup) | PR-2 ✅ |
| (KFP pipeline param) `vector_search_index_resource_name` | string | `""` | embed pipeline の VVS upsert gate (空なら no-op) | PR-3 ✅ |
| (KFP pipeline param) `enable_vector_search_upsert` | bool | `false` | manifest メタデータに乗る gate (Cloud Function runner で消費予定) | PR-3 ✅ |
| (KFP pipeline param) `vector_search_upsert_batch_size` | int | `500` | upsert chunk size | PR-3 ✅ |

**変更**: 計画段階の旧 env 案 / `ENABLE_VECTOR_SEARCH_UPSERT` は廃止。FOS は `FEATURE_FETCHER_BACKEND` group で統一、VVS upsert は KFP pipeline parameter として表現 (env で gate しない設計に変更)。

`infra/manifests/search-api/configmap.example.yaml` への env 反映は **Wave 2 (manifest apply とまとめる)** に deferred。

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

### 4.1 Terraform モジュール / リソース (W2-1 / W2-2)

**新規実装が必要な Terraform**:

- [x] **W2-1**: **`infra/terraform/modules/vector_search/`** を実装 (Wave 1 PR-1 が `app/services/adapters/vertex_vector_search_semantic_search.py` を空 endpoint で先行追加済、本ステップで実 resource を provision)
  - `main.tf` — `google_vertex_ai_index` + `google_vertex_ai_index_endpoint` + `google_vertex_ai_index_endpoint_deployed_index_resource`
  - `variables.tf` — `dimensions = 768` (`ml/common/config/embedding.py` と一致)、`distance_measure = "COSINE_DISTANCE"`、`approximate_neighbors_count` etc.
  - `outputs.tf` — `index_endpoint_id` / `deployed_index_id` / `index_resource_name` を runtime ConfigMap / IAM / pipeline param に伝搬
- [x] **W2-1**: `infra/terraform/environments/dev/main.tf` で `module "vector_search"` を有効化 + 出力を root outputs / search-api ConfigMap / pipeline param へ伝搬

**既存 Terraform の設定変更**:

- [x] **W2-2**: `infra/terraform/modules/vertex/variables.tf::enable_feature_online_store` の default を `true` に変更 (`mlops-dev-a` PDCA 都合は `terraform.tfvars` で override 可)。**Feature View** (`property_features` を source とする View) も同モジュールで provision する実装を追加し、Feature View ID と regional public endpoint URL を outputs に追加 (Wave 1 PR-2 が `vertex_feature_view_id` / `vertex_feature_online_store_endpoint` を settings に予約済)
- [x] **W2-4 Stage 1**: `infra/terraform/modules/composer/` を Phase 7 で **本実装** (新規 4 ファイル: main.tf / variables.tf / outputs.tf / versions.tf、`enable_composer=false` default で count=0 = no-op skeleton)。`infra/terraform/environments/dev/main.tf` で `module "composer"` を呼び出し、`module.iam.service_accounts.composer.email` を渡す。詳細 checklist は §4.7

### 4.2 IAM / Workload Identity (W2-3)

Wave 1 の env 切替を活かすには、KServe / search-api / pipeline SA から VVS / FOS / Feature View へ access できる WI bind が必要:

- [x] `infra/terraform/modules/iam/main.tf` の現状確認 — `sa-api` には既に `roles/aiplatform.user` 付与済 ✓、`sa-pipeline` / `sa-pipeline-trigger` も同様 ✓
- [x] **新規 (W2-3-a)**: search-api KSA → `sa-api` (WI bind) は `roles/aiplatform.user` 付与で VVS `find_neighbors` / Feature View `fetch_feature_values` を許可 ([infra/terraform/modules/iam/main.tf:148-152](../../infra/terraform/modules/iam/main.tf#L148-L152))。実走で `ops-search` / `ops-vertex-vector-search-smoke` / `ops-vertex-feature-group` が PASS しており IAM 不足は無し
- [x] **新規 (W2-3-b)**: KServe encoder/reranker KSA → 専用 GCP SA (`sa-endpoint-encoder` / `sa-endpoint-reranker`) に bind 済 ([infra/terraform/modules/iam/main.tf:33-41](../../infra/terraform/modules/iam/main.tf#L33-L41))。reranker SA に `roles/aiplatform.user` 付与済 ([infra/terraform/modules/iam/main.tf:262-266](../../infra/terraform/modules/iam/main.tf#L262-L266))。encoder は最小権限維持 (Vertex API 呼び出し不要)
- [x] **新規 (W2-3-c)**: `sa-pipeline` に `roles/aiplatform.user` 付与済 ([infra/terraform/modules/iam/main.tf:196-200](../../infra/terraform/modules/iam/main.tf#L196-L200))。`backfill_vector_search_index --apply` が live で完走しており upsert 権限不足は無し
- [x] **W2-4 関連 (Stage 1)**: Composer 環境の SA 着地済 ([infra/terraform/modules/iam/main.tf:267-322](../../infra/terraform/modules/iam/main.tf#L267-L322)) — `sa-composer` に `roles/composer.worker` / `roles/aiplatform.user` / `roles/bigquery.{jobUser,dataViewer}` / `roles/run.invoker` 付与、deployer SA に `roles/composer.admin` 追加、`outputs.tf` の `service_accounts` map に `composer` entry 追加

### 4.3 Manifests (W2-5、Wave 1 deferred 含む)

- [x] **W2-5-a**: `infra/manifests/search-api/configmap.example.yaml` に新 env vehicle を追加 — Wave 1 の暫定切替 env。Wave 2 後に削除前提で、現時点では空 placeholder を持つ:
  - `SEMANTIC_BACKEND` (default `bq`)
  - `VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID` / `VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID`
  - `FEATURE_FETCHER_BACKEND` (default `bq`)
  - `VERTEX_FEATURE_ONLINE_STORE_ID` / `VERTEX_FEATURE_VIEW_ID` / `VERTEX_FEATURE_ONLINE_STORE_ENDPOINT`
- [x] **W2-5-b**: `infra/manifests/search-api/deployment.yaml` の env で上記を ConfigMap から参照 (Wave 2 後に削除するまでの暫定配線)
- [x] **W2-5-c**: ConfigMap generator (`scripts/ci/sync_configmap.py`) は Wave 2 キーを再現するところまで追従済。**残タスク**は §4.1 W2-1 / W2-2 の Terraform outputs を `scripts.setup.deploy_all` live overlay へ接続すること
- [x] **PR-4 deferred 解消**: `infra/manifests/kserve/reranker.yaml` の env vehicle は不要 → search-api ConfigMap 経由で完結。原本記述は不要、Wave 1 PR-4 docstring の予告は close

### 4.4 ops スクリプト / one-off (W2-6 / W2-7)

- [x] **W2-6**: `scripts/setup/backfill_vector_search_index.py` (初回 backfill 用 one-off。`feature_mart.property_embeddings` 全行を読み出し → `MatchingEngineIndex.upsert_datapoints` で push、batch size = 500 = Wave 1 PR-3 の `vector_search_upsert_batch_size` default と一致)
- [x] **W2-7-a**: `scripts/ops/vertex/vector_search.py` (smoke 用、`find_neighbors` を直接叩いて top-K を表示)
- [x] **W2-7-b**: `scripts/ops/vertex/feature_group.py` の既存 smoke を `FEATURE_FETCHER_BACKEND=online_store` 切替後の経路 (Feature View 経由) で確認済。search-api ConfigMap も live canonical 値へ flip 済
- [x] **W2-7-c**: `tests/integration/parity/test_semantic_backend_parity.py` (BQ vs VVS 上位 K diff) と `test_feature_fetcher_parity.py` (BQ vs FOS feature 値 diff) の **live GCP marker 付き雛形**を実装済。**残タスク**は Wave 2 live 環境で env を投入して実行・閾値調整すること

### 4.5 deploy / CI 統合 (W2-7)

- [x] `make deploy-all` の wiring に `module.vector_search` を tf apply 順序へ組み込み済 ([scripts/setup/deploy_all.py](../../scripts/setup/deploy_all.py) の `_steps()` で `tf-apply` (stage1+stage2) → `seed-test` → `sync-meili` → `backfill-vvs` → `trigger-fv-sync` → `apply-manifests` → `overlay-configmap` → `deploy-api`)
- [ ] `scripts.deploy.monitor` に vector_search smoke step を追加 (`find_neighbors` を 1 回叩いて 200 確認) — `make run-all-core` 内で `ops-vertex-vector-search-smoke` が走るので冗長化、優先度低
- [x] `make run-all-core` に `ops-vertex-vector-search-smoke` を追加 (PDCA loop で smoke 自動化)
- [x] `make run-all-core` に `ops-vertex-feature-group` を追加 (Feature View fetch を本線へ昇格)
- [x] `make run-all-core` に `ops-train-wait` を追加 (`ops-train-now` submit だけで終わらせず、SUCCEEDED まで待つ)
- [ ] `make composer-deploy-dags` (Phase 6 から継承) が Phase 7 環境でも DAG deploy できることを確認 (§4.7)

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
- [x] **mypy pre-existing 負債** (PR-1 audit で発見): `app/services/search_service.py` / `app/services/adapters/lexical_search.py` / `app/api/routers/ops_router.py` / `tests/conftest.py` の対象 9 件は解消済
- [x] **`tests/integration/parity/`** に live GCP 比較 test の雛形を追加 (`test_semantic_backend_parity.py` / `test_feature_fetcher_parity.py`、§4.4 W2-7-c と統合)。実行は Wave 2 live 環境で行う

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
