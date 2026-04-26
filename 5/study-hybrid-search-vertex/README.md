# study-hybrid-search-vertex

Phase 5 は、Phase 4 の不動産ハイブリッド検索を維持したまま、**Vertex 標準 MLOps** を実コードへ統合するフェーズ。

不変の検索中核:

- `Meilisearch`
- `BigQuery VECTOR_SEARCH`
- `multilingual-e5`
- `RRF`
- `LightGBM LambdaRank`

変えるのは検索コアではなく、MLOps の実行責務。

## Phase 5 の主役

| 技術 | 役割 |
|---|---|
| Vertex AI Pipelines | 学習・埋め込み DAG |
| Vertex AI Endpoints | encoder / reranker 推論 |
| Model Registry | モデル版管理 |
| Feature Group | 特徴量管理補助 |
| Model Monitoring | drift 監視 |

## この Phase でやらないこと

- BQML
- Dataflow
- Monitoring SLO
- Explainable AI
- GKE / KServe

加えて親リポ `README.md` §1 / `docs/02_移行ロードマップ.md §1.4` に列挙された全 Phase 共通禁止技術は本 Phase でも扱わない。

## ドキュメント

- [docs/02_移行ロードマップ.md](docs/02_移行ロードマップ.md): Phase 5 の決定的仕様
- [docs/01_仕様と設計.md](docs/01_仕様と設計.md): 実装配置
- [docs/03_実装カタログ.md](docs/03_実装カタログ.md): 実装棚卸し
- [docs/04_運用.md](docs/04_運用.md): 運用手順
- [CLAUDE.md](CLAUDE.md): 作業ガイド
