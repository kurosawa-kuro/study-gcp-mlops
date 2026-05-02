# TASKS.md (Phase 7 — current sprint)

`docs/TASKS_ROADMAP.md` (長期 backlog/index、554 行) の current-sprint 抜粋。Claude Code の新セッションで「今 sprint で何をやり、何をやらないか」を最初に確認する単一エントリポイント。詳細は `TASKS_ROADMAP.md` 本体、過去判断履歴は `docs/decisions/` (ADR 0001〜0008)。

権威順位: `TASKS_ROADMAP.md > TASKS.md > 01_仕様と設計.md > README.md`。

## 現在の目的

Phase 7 = Phase 6 (PMLE + Composer 本線) と Phase 5 必須の Feature Store / Vertex Vector Search を継承し、**serving 層のみ Vertex AI Endpoint → GKE + KServe InferenceService に差し替える** 到達ゴール。

中核 (不動産ハイブリッド検索 / Meilisearch + Vertex Vector Search + ME5 + RRF + LightGBM LambdaRank) は不変。推論を cluster-local HTTP に委譲。

Phase 7 固有: KServe → Feature Online Store を **Feature View 経由で** opt-in 参照、TreeSHAP 用 explain 専用 Pod を独立 deploy。

## 進捗サマリ (2026-05-02 時点 — `TASKS_ROADMAP.md §進捗サマリ` 抜粋)

| Wave | フェーズ | 状態 | 内容 |
|---|---|---|---|
| **Wave 1** | ローカル完結 (検索アプリ層) | **✅ 完了 (M-Local 達成)** | PR-1 〜 PR-4 全 merge、`make lint` / `make fmt-check` / 関連 mypy / pytest 63 passed |
| **Wave 2** | GCP インフラ層 (クラウド側主作業) | 🟡 live 検証中 | local ADC-free boot、G3-G8 (`ops-search-components` / VVS / FOS / feedback / ranking / accuracy / retrain wait) は実測 PASS。canonical ConfigMap auto-flip も実装済。未完了は full PDCA 完走、Composer 継承確認、互換レイヤのコード削除 |
| **Wave 3** | docs / reference architecture 整合 | ⏳ Wave 2 後 | `03_実装カタログ.md` / `05_運用.md` の semantic / feature / Composer 経路記述を Wave 1/2 に追従 |

## 今回の作業対象 (Wave 2 の残り)

`TASKS_ROADMAP.md §4` (Wave 2) を正本として以下を残作業として扱う:

- [ ] `infra/terraform/modules/vector_search/` の **live apply** + deployed index の作成
- [x] `enable_feature_online_store` を `dev` で `true` に flip + Feature View outputs 反映の live apply
- [ ] **Composer 継承確認**: Phase 6 の `daily_feature_refresh` / `retrain_orchestration` / `monitoring_validation` 3 DAG が Phase 7 環境でも稼働すること
- [ ] **live GCP smoke**: `tests/integration/parity/test_semantic_backend_parity.py` / `test_feature_fetcher_parity.py` の `live_gcp` marker 付きを実 GCP で実行
- [ ] **互換レイヤ削除** (Wave 2 完了後): `BigQuerySemanticSearch` / `BigQueryFeatureFetcher` / `SEMANTIC_BACKEND` / `FEATURE_FETCHER_BACKEND` env / legacy alias を撤去し、canonical 1 本に収束
- [ ] `scripts/setup/backfill_vector_search_index.py` の live 実行 (BQ embedding → VVS index 初回 backfill)
- [x] `scripts/ops/vertex/vector_search.py` smoke の live 実行
- [x] `scripts/ops/vertex/feature_group.py` smoke の live 実行
- [x] `make ops-feedback` / `make ops-ranking` / `make ops-accuracy-report` の live 実行
- [x] `ops-train-wait` 追加 (`ops-train-now` submit 後に SUCCEEDED まで待つ contract)

## 今回はやらない

- 中核 5 要素の置換 (Meilisearch → Elasticsearch 等) — User 合意必須
- `/search` デフォルト挙動の変更 — User 合意必須
- 全 Phase 共通禁止技術 (Agent Builder / Discovery Engine / Gemini RAG / Model Garden / Vizier / W&B / Looker Studio / Doppler)
- BigQuery fallback / backend 切替 env を「default off で残す」運用 — 教育コード原則として **撤去** (`TASKS_ROADMAP.md §2.1` / `§2.4`)

## 完了条件

- [ ] `make check` (ruff + format + mypy strict + pytest) 通過
- [ ] `make deploy-all` 完了 (tf-bootstrap → tf-init → WIF 復元 → sync-dataform-config → tf-plan → tf apply → deploy-api、約 12-15 分)
- [ ] `make run-all-core` 通過 (check-layers → seed-test → sync-meili → ops-train-now → ops-train-wait → ops-livez/search/search-components/VVS/FOS/feedback/ranking/label-seed → ops-daily → ops-accuracy-report)
- [ ] Composer 3 DAG が retrain schedule の本線として稼働
- [ ] `/search` semantic 経路が Vertex Vector Search 1 本 (BQ fallback 撤去後)
- [ ] feature 取得経路が Feature Online Store (Feature View 経由) 1 本 (BQ direct fetch 撤去後)
- [ ] Feature parity invariant 6 ファイル原則 (CLAUDE.md §「Feature parity invariant」) を維持

## 実装済 (Wave 1 + Wave 2 offline 部分)

### Wave 1 (`TASKS_ROADMAP.md §3` / 63 unit tests passed)
- [x] PR-1: `SemanticSearch` Port + `vertex_vector_search_semantic_search.py` adapter (17 tests)
- [x] PR-2: `FeatureFetcher` Port + Feature Online Store adapter (18 tests)
- [x] PR-3: `VectorSearchWriter` Port + pipeline component (17 tests)
- [x] PR-4: Container 配線 + `ranking.py` merge (11 tests)

### Wave 2 offline wiring (`TASKS_ROADMAP.md §4`)
- [x] W2-1: `infra/terraform/modules/vector_search/` module (main/variables/outputs/versions.tf) 新規
- [x] W2-2: `vertex/variables.tf` で `enable_feature_online_store` default `true` + Feature View outputs
- [x] W2-3: KServe SAs (vector search query / feature view read) IAM bindings (`modules/iam`)
- [x] W2-5: `search-api configmap.example` + `deployment.yaml` の env vehicle 追加
- [x] W2-6: `scripts/setup/backfill_vector_search_index.py` の実装
- [x] W2-7-a: `scripts/ops/vertex/vector_search.py` smoke の実装
- [x] `scripts/ci/sync_configmap.py` 追従 (`semantic_backend` / `vertex_vector_search_*` / `feature_fetcher_backend` / `vertex_feature_*` を generator が再現)
- [x] `tests/integration/parity/` の live GCP 雛形追加 (`live_gcp` marker で local skip)
- [x] W2-9: mypy pre-existing 9 件解消 (KFP 2.16 互換 issue のみ継続)

## 次 Phase

Phase 7 が到達ゴール。これ以降の phase は無い (`README.md` / 親 `CLAUDE.md` で 7 phase 構成と明記)。

## 参照

- `TASKS_ROADMAP.md` (本ファイルの正本、Wave 1/2/3 詳細)
- `docs/decisions/0001〜0008` (恒久対処ギャップの ADR)
- 親 `CLAUDE.md §「Cloud Composer (Phase 6 必須、Phase 7 継承)」` (orchestration 二重化禁止)
