# study-hybrid-search-pmle

**Phase 5 (`5/study-hybrid-search-vertex/`) の不動産ハイブリッド検索実装に、GCP Professional Machine Learning Engineer (PMLE) 試験範囲の 8 技術を実際に統合して動くコードとして学ぶ** フェーズ。Phase 3-5 で積んだ Port/Adapter 思想の延長線上で、新技術を adapter / 副経路 / 追加エンドポイント / 追加 pipeline として既存コードに組み込む。

> **不変 (絶対に変えない)**: 題材 (不動産ハイブリッド検索) と中核コード (Meilisearch BM25 + BQ `VECTOR_SEARCH` + ME5 + RRF + LightGBM LambdaRank の挙動 / デフォルトの `/search` 応答)。それ以外 (新 adapter / 新エンドポイント / 新 pipeline / 新 Terraform / reranker endpoint への `explanation_spec` 追加 等) は PMLE 学習のため自由に変えてよい。詳細は [`docs/02_移行ロードマップ.md §0`](docs/02_移行ロードマップ.md)。

本 README は「機能の簡易説明 + 各ドキュメントへのリンク」だけを扱う (`docs/README.md §1` の規約に従う)。Phase 6 の意思決定は [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) が正本、統合トピックの詳細設計は [`docs/01_仕様と設計.md §3`](docs/01_仕様と設計.md)。

## Phase 6 の位置付け

- **Phase 3-5**: 不動産ハイブリッド検索のドメインを固定し、実行基盤 (Local → GCP → Vertex AI) を段階的に差し替える
- **Phase 6 (本フェーズ)**: Phase 5 完成系を基盤として PMLE 試験範囲の 8 技術を **adapter / 新規コンポーネントとして実コードに統合**。Phase 3-5 の「設計思想は一貫、adapter を差し替え」の思想そのものを、新技術導入の形で実践する
- **Phase 7 (Optional)**: Phase 5 の serving 層のみ GKE + KServe へ差し替える Draft

## 統合する PMLE 8 技術

各技術を Phase 5 実コードのどこに組み込むかの 1 行サマリ。詳細設計は [`docs/01_仕様と設計.md §3`](docs/01_仕様と設計.md)、実装順序は [`docs/02_移行ロードマップ.md §4.1`](docs/02_移行ロードマップ.md)。

| # | 技術 | 統合先 / 変更範囲 |
|---|---|---|
| T1 | **BQML** | `app/adapters/bqml_popularity_scorer.py` + `scripts/bqml/train_popularity.sql`。補助スコアとして rerank feature に加算 (flag で opt-in、parity 6 ファイル同 PR) |
| T2 | **Dataflow** | `ml/streaming/` 新設。Pub/Sub `ranking-log` → windowed CTR → BQ `ranking_log_hourly_ctr`。既存 BQ Subscription と並列 |
| T3 | **Vertex Vector Search** | `app/adapters/vertex_vector_search_retriever.py` (alternative SemanticRetriever)。`SEMANTIC_BACKEND=bq\|vertex` flag、default=bq |
| T4 | **Explainable AI** | reranker Vertex Endpoint に `explanation_spec` 追加 + `ml/serve/reranker_server.py` に explain() 実装 + `/search?explain=true` で attribution 返却 |
| T5 | **Monitoring SLO** | `infra/modules/slo/` 新設。availability 99.0% / latency p95 < 500ms + burn-rate AlertPolicy |
| T6 | **RAG (Gemini)** | `app/adapters/gemini_generator.py` + `services/rag_summarizer.py` + 新エンドポイント `/rag` |
| T7 | **Agent Builder** | `app/adapters/agent_builder_lexical.py` (alternative LexicalRetriever、副経路)。`LEXICAL_BACKEND=meili\|agent_builder` flag、default=meili (非負制約) |
| T8 | **Model Garden (Gemini)** | `ml/embed/.../components/enrich_with_gemini.py` (optional KFP component)。description を構造化して `properties_enriched` に書き出し |

**default flag では Phase 5 挙動 (中核コード) が維持される**。PMLE 技術は opt-in で有効化して学ぶ。

## ディレクトリ

```text
6/study-hybrid-search-pmle/
├── README.md / CLAUDE.md
├── docs/                # 更新対象 (02 → 01 → README → CLAUDE の権威順位)
├── app/                 # FastAPI + Port/Adapter。Phase 6 で新 adapter / 新エンドポイント追加
├── ml/                  # pipeline / embed / train / serve / sync。Phase 6 で streaming/ 新設 + enrich component
├── pipeline/            # KFP entrypoints。Phase 6 で embed pipeline に optional component 追加
├── infra/               # Terraform。Phase 6 で slo/ / vector_search/ / streaming/ / agent_builder/ 新モジュール
├── scripts/             # ops / deploy / setup / bqml/ (新設)
├── tests/               # arch / parity / infra。Phase 6 追加コードも parity / 境界検知を維持
├── monitoring/          # feature skew SQL
├── env/                 # config/setting.yaml (semantic_backend / lexical_backend flag 追加)
├── tools/
└── pyproject.toml / uv.lock / Makefile / .github/
```

Phase 5 からの具体的な差分は [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md) を各統合 PR で追記していく。

## 学習の進め方

1. [`docs/02_移行ロードマップ.md §0`](docs/02_移行ロードマップ.md) で **不変 = 題材 + ハイブリッド検索中核コード** を腹落ちさせる
2. [`docs/02_移行ロードマップ.md §3`](docs/02_移行ロードマップ.md) で 8 技術の統合先サマリを読む
3. [`docs/01_仕様と設計.md §3`](docs/01_仕様と設計.md) で各トピックの **ファイル配置 / Port / Adapter / feature flag** を確認
4. [`docs/01_仕様と設計.md §5`](docs/01_仕様と設計.md) の実装順序 (T5 → T4 → T3 → T6 → T1 → T8 → T2 → T7) に沿って、**1 PR = 1 トピック** で統合を進める
5. 各 PR で `make check` + parity test + Port/Adapter 境界検知を PASS させる
6. Terraform 変更は `make tf-plan` → `make tf-apply` 経由 (手で `gcloud` を叩かない)

## 非負制約 (Phase 6)

詳細は [`docs/02_移行ロードマップ.md §0`](docs/02_移行ロードマップ.md)。

- **不変**: 題材 (不動産ハイブリッド検索) / ハイブリッド検索中核 (LightGBM + ME5 + Meilisearch + BQ VECTOR_SEARCH + RRF) / `/search` デフォルト応答 / 親リポ非負制約 (GCP プロジェクト / リージョン / Python 3.12 / uv / Terraform 1.9+ / WIF)
- **自由**: 中核以外の改変 (新 Port / adapter / service / endpoint / pipeline / Terraform モジュール / parity 6 ファイル同 PR 更新 等)

## ドキュメント

初回は Phase 6 のスコープ (`docs/02_移行ロードマップ.md`) → 統合トピック詳細 (`docs/01_仕様と設計.md §3`) の順に読む。

| ドキュメント | 目的 | 主な読者 |
|---|---|---|
| [`docs/README.md`](docs/README.md) | ドキュメント運用ルール (役割 / 権威順位 / 更新規約 / 書き方) | 文書を触る人全員 |
| [`docs/01_仕様と設計.md`](docs/01_仕様と設計.md) | PMLE 試験範囲マップ + 8 統合トピックの詳細設計 (ファイル / Port / Adapter / flag) + 実装順序 | LLM / 学習者 |
| [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) | **本 Phase の決定的仕様** (不変の中核 / 採用 / 不採用 / 統合トピック一覧) | LLM / 学習者 |
| [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md) | 実装カタログ (Phase 5 継承 + Phase 6 で追加したもの、統合 PR ごとに追記) | 新規参加者 / LLM |
| [`docs/04_運用.md`](docs/04_運用.md) | 環境構築 + 定常運用 + Phase 6 で追加した ops-* make target | 新規参加者 / 運用担当 |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 向け作業ガイド (Phase 6 非負制約 / 統合トピック運用ルール) | Claude Code |

ドキュメントが互いに矛盾したときの勝者は `docs/02_移行ロードマップ.md` (詳細は `docs/README.md §2` 権威順位)。
