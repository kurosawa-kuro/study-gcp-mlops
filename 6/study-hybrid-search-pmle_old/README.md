# study-hybrid-search-pmle

Phase 6 は、Phase 5 の不動産ハイブリッド検索実装を維持したまま、PMLE 学習向けの追加技術を **実コードへ bolt-on で統合する** フェーズ。

不変なのは次の中核経路。

- `Meilisearch` lexical search
- `BigQuery VECTOR_SEARCH` semantic search
- `multilingual-e5`
- `RRF`
- `LightGBM LambdaRank`

`Meilisearch` は学習用ローカル構成や段階導入で扱いやすく、`Elasticsearch` より導入しやすいため継続採用する。

## Phase 6 の位置付け

- Phase 3-5: ハイブリッド検索の中核を育てる
- Phase 6: 中核を維持したまま PMLE 追加技術を積み増す
- Phase 7: serving 層を GKE / KServe に差し替える

## Phase 6 で扱う技術

| # | 技術 | 統合先 |
|---|---|---|
| T1 | BQML | popularity 補助スコア |
| T2 | Dataflow | ranking-log 集計 |
| T4 | Explainable AI | reranker explain |
| T5 | Monitoring SLO | Cloud Run 運用監視 |
| T6 | RAG (Gemini) | `/rag` endpoint |
| T8 | Model Garden enrichment | `properties_enriched` 生成 |

削除済みの旧追加機能は本 Phase の対象外。

## ドキュメント

- [docs/02_移行ロードマップ.md](docs/02_移行ロードマップ.md): Phase 6 の決定的仕様
- [docs/01_仕様と設計.md](docs/01_仕様と設計.md): 実装配置
- [docs/03_実装カタログ.md](docs/03_実装カタログ.md): 実装棚卸し
- [docs/04_運用.md](docs/04_運用.md): 運用手順
- [CLAUDE.md](CLAUDE.md): 作業ガイド
