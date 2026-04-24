# CLAUDE.md

本リポジトリ (`6/study-gcp-ml-engineer-cert`) で作業する Claude Code 向けのガイド。**Phase 6 は Phase 5 (`5/study-hybrid-search-vertex/`) 完成系に PMLE 試験範囲の 8 技術を adapter / 新規コンポーネントとして統合するフェーズ**。Phase 3-5 の Port/Adapter 思想そのものを新技術導入の形で実践する。

ドキュメント全般の運用規約は [`docs/README.md`](docs/README.md)、スコープの決定権は [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md)。本 CLAUDE.md はそれらに従属する。

---

## 最初に読むもの (順番)

1. [`docs/02_移行ロードマップ.md §0`](docs/02_移行ロードマップ.md) — **不変は「ハイブリッド検索というテーマと中核コード」のみ**
2. [`docs/02_移行ロードマップ.md §3`](docs/02_移行ロードマップ.md) — 8 統合トピックのサマリ
3. [`docs/01_仕様と設計.md §3`](docs/01_仕様と設計.md) — 各トピックの **ファイル配置 / Port / Adapter / feature flag** 詳細
4. [`docs/01_仕様と設計.md §5`](docs/01_仕様と設計.md) — 実装順序 (T5 → T4 → T3 → T6 → T1 → T8 → T2 → T7)
5. [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md) + [`docs/04_運用.md`](docs/04_運用.md) — Phase 5 継承の実装 / 運用詳細

---

## 非負制約 (User 確認無しに変えない)

### 不変 — 絶対に変えない

| 項目 | 値 |
|---|---|
| **題材 / ドメイン** | 不動産ハイブリッド検索 (クエリ + フィルタ → 物件ランキング上位 20 件) |
| **ハイブリッド検索中核** | Meilisearch BM25 (lexical) + BQ `VECTOR_SEARCH` + multilingual-e5 (semantic) + RRF 融合 + LightGBM LambdaRank (rerank) の挙動 / データフロー / デフォルト `/search` レスポンス |
| **親リポ非負制約** | GCP プロジェクト `mlops-dev-a` / リージョン `asia-northeast1` / Python 3.12 / uv workspace / Terraform 1.9+ / WIF (SA Key 禁止) / 10 SA 最小権限分離 |
| **default feature flag 値** | Phase 6 で追加する flag (`SEMANTIC_BACKEND` / `LEXICAL_BACKEND` / `BQML_POPULARITY_ENABLED` 等) は default で Phase 5 挙動を維持する値にする (`bq` / `meili` / `false`) |

中核を **置換 / 削除 / 無効化する変更はしない**。親 CLAUDE.md の「ハイブリッド検索の基本構成は LightGBM + multilingual-e5 + Meilisearch + RRF + LambdaRank を必須」をそのまま継承する。

### 自由 — PMLE 学習のため積極的に変えてよい

中核 (上表) 以外はすべて積極的に変えてよい:

- 新 Port / Adapter / Service / Entrypoint の追加 (`app/src/app/**`)
- 新エンドポイント追加 (`/rag` / `/search?explain=true` 等)
- 既存 adapter への機能追加 (例: reranker に `explanation_spec`)
- 新 KFP component 追加 (`ml/embed/.../components/` / `ml/streaming/` 新ワークスペース)
- 新 Terraform モジュール追加 (`infra/modules/{slo,vector_search,streaming,agent_builder}/`)
- 新 feature 列追加 (parity 6 ファイルを同 PR で揃える前提)
- 既存 `pyproject.toml` への依存追加 (`google-genai` / `apache-beam` / `google-cloud-discoveryengine` 等)
- 新 SA 追加 (例: `sa-dataflow`)、既存 SA への IAM 追加 (例: `sa-api` に Vertex Vector Search 読み取り権限)
- 新 make target 追加 (`make bqml-train-popularity` / `make deploy-streaming` / `make ops-slo-status` 等)
- 新 CI workflow 追加 (`.github/workflows/deploy-streaming.yml` 等)

### NG (やり方として誤り、User が明確に拒否した)

- ❌ `labs/<topic>/` のように **既存コードから隔離された手順書 / GUI ノート** を書いて「学習した」ことにする
- ❌ **問題集 / Q&A** をドキュメントに書き連ねる (学習は動くコードで行う)
- ❌ 「Phase 5 コード全体をなるべく変えない」を非負制約に置く (中核以外の改変は Phase 6 の主目的)
- ❌ Terraform を通さずに `gcloud` / `bq` を手で叩いてリソースを作る (`labs/` の時の誘惑)

---

## Phase 6 での作業スタイル

Phase 3-5 の延長線上で **Port/Adapter を維持したまま新 adapter / 新コンポーネントを追加する** のが主な作業:

1. **1 PR = 1 統合トピック** (T1〜T8 のいずれか)。parity 波及がある場合は 6 ファイル同 PR で揃える
2. **Port を増やす** (新 Protocol を `ports/<name>.py` に)、または既存 Port の alternative adapter を追加する
3. **Adapter の外部 SDK import は adapter 層限定** (`google.cloud.*` / `google.genai` / `apache_beam` / `google.cloud.discoveryengine` は `adapters/` でのみ import)
4. **composition root で feature flag による切り替え** を実装 (`app/src/app/entrypoints/api.py::lifespan`)
5. **`make check` を PASS** (ruff / ruff format / mypy strict / pytest)、**`make check-layers` を PASS** (境界違反なし)、**parity test を PASS** (6 ファイル)
6. **Terraform で宣言**、`make tf-plan` で差分確認 → `make tf-apply` で反映
7. **新 make target / 新 ops-* コマンド** は `docs/04_運用.md` に同 PR で追記
8. **学習終了後の coast-down 手順** (常時課金リソースの destroy) を `make destroy-*` に追加

### 実装順序 (`docs/01_仕様と設計.md §5`)

1. **T5 Monitoring SLO** (Terraform のみ、parity 影響ゼロ、最小リスク) — 最初に着手
2. **T4 Explainable AI** (reranker endpoint 拡張 + `/search?explain=true`)
3. **T3 Vertex Vector Search** (alternative semantic adapter + Terraform)
4. **T6 RAG (Gemini)** (新エンドポイント `/rag`、既存 /search 不変)
5. **T1 BQML** (parity 6 ファイル全更新、影響大)
6. **T8 Model Garden enrichment** (KFP pipeline に optional component)
7. **T2 Dataflow** (新ワークスペース + 新 SA + Flex Template、規模最大)
8. **T7 Agent Builder** (Meilisearch adapter 抽出リファクタ前提、最後)

学習上の優先度で順番を入れ替える判断は User が行う。

---

## Port / Adapter 境界と make check

Phase 6 追加コードも Phase 5 と同じ境界ルールに従う:

- **Port**: `<workspace>/src/<pkg>/ports/<name>.py` の Protocol。`ports/__init__.py` で re-export
- **Adapter**: `<workspace>/src/<pkg>/adapters/<name>.py`。外部 SDK 依存はここでのみ
- **Service**: `<workspace>/src/<pkg>/services/<name>.py`。Port だけ import、adapter import 禁止
- **境界検知**: `scripts/checks/layers.py::RULES` に新 Port / service を追加。`make check-layers` で CLI、`tests/arch/test_import_boundaries.py` で CI

Phase 6 で追加される主な外部 SDK 依存:

| SDK | import OK なファイル |
|---|---|
| `google.cloud.bigquery` | `adapters/bqml_popularity_scorer.py` / 既存 adapters |
| `google.cloud.aiplatform` | `adapters/vertex_vector_search_retriever.py` / 既存 adapters |
| `google.genai` (または `vertexai.generative_models`) | `adapters/gemini_generator.py` |
| `apache_beam` | `ml/streaming/src/streaming/**` (adapter 相当) |
| `google.cloud.discoveryengine` | `adapters/agent_builder_lexical.py` |

---

## Feature parity invariant (6 ファイル同 PR 原則、継承)

Phase 5 から継承。特徴量を追加 / 変更するとき、以下 6 つを必ず同じ PR で揃える:

1. `definitions/features/property_features_daily.sqlx`
2. `common/src/common/feature_engineering.py::build_ranker_features`
3. `common/src/common/schema/feature_schema.py::FEATURE_COLS_RANKER`
4. `infra/terraform/modules/data/main.tf` の `ranking_log.features` RECORD
5. `monitoring/validate_feature_skew.sql` の UNPIVOT
6. `infra/modules/vertex/main.tf::google_vertex_ai_feature_group_feature` × N

Phase 6 で **T1 BQML 補助スコアを rerank feature に加算する** ケース、**T8 enrichment で新列を追加する** ケースは上記すべての更新が必要。parity test (`tests/parity/test_feature_parity_*.py`) が FAIL するので CI で検知される。

---

## ドキュメント衝突時の権威順位

`docs/README.md §2` に従う:

```
02_移行ロードマップ.md > 01_仕様と設計.md > README.md
```

`CLAUDE.md` と `03_実装カタログ.md` / `04_運用.md` は上位から派生する従属ドキュメント。矛盾したら `02_移行ロードマップ.md` を正として他を合わせ、User に flag する。

Phase 6 で特に drift しやすいのは:

- 「不変の範囲」の表現 (「Phase 5 コード全体」と書かれていたら誤り、「ハイブリッド検索中核」が正)
- 「統合トピックのファイル配置」(01 §3 と 02 §3 の表が食い違っていないか)

---

## 学習リポとしての最小スペック選定 (継承)

Vertex Endpoint / Vector Search endpoint / Dataflow job / Agent Builder Engine はすべて **min=1 / max=1 / 小型マシン** を default にする。Phase 5 からの非負制約を継承。

常時課金されるサービス (Vector Search endpoint / Dataflow streaming job / Agent Builder Engine) は `make destroy-*` でいつでも消せる形にして、学習セッションが終わったら destroy する運用。

---

## 書き方

`docs/README.md §4` 書き方ルールに従う:

- 日本語で書く。英単語は技術用語としてそのまま (`lifespan`, `Booster`, `explanation_spec`, `burn rate`, `Flex Template` 等)
- コマンドは `make` ターゲット優先。生 `gcloud` / `bq` / `terraform` は動的引数が必要な場合のみ
- 識別子は固有名を使う (`<foo>` でぼかさない)
- STEP / 番号付きリストは上から叩けば成立する順序で書く
- 推測で書かない。コマンドを書いたら実際に叩いて確認する (Terraform は `make tf-plan` で差分を見てから apply)
