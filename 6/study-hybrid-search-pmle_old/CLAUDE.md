# CLAUDE.md

> **ARCHIVED.** 現行の Phase 6 は [`../study-hybrid-search-pmle/CLAUDE.md`](../study-hybrid-search-pmle/CLAUDE.md)。本ディレクトリは親 [`CLAUDE.md`](../../CLAUDE.md) §「フェーズ横断の原則」で archive と明示されている。**参照のみ可、修正は user 明示指示のみ。**

Phase 6 (`study-hybrid-search-pmle`) で作業するときのガイド。正本は [docs/02_移行ロードマップ.md](docs/02_移行ロードマップ.md)。

## 最初に読むもの

1. [docs/02_移行ロードマップ.md](docs/02_移行ロードマップ.md)
2. [docs/01_仕様と設計.md](docs/01_仕様と設計.md)
3. [docs/03_実装カタログ.md](docs/03_実装カタログ.md)
4. [docs/04_運用.md](docs/04_運用.md)

## 不変ルール

- 題材は不動産ハイブリッド検索のまま
- `/search` 既定挙動は Phase 5 と一致
- 中核構成 `LightGBM + multilingual-e5 + Meilisearch + BigQuery VECTOR_SEARCH + RRF` は維持
- 新技術は bolt-on として追加し、既定経路を置換しない

## Phase 6 の対象

- BQML
- Dataflow
- Explainable AI
- Monitoring SLO
- RAG (Gemini)
- Model Garden enrichment

削除済みの旧追加機能は対象外。

## 実装ルール

- Port は `app/services/protocols/`
- 外部 SDK は `app/services/adapters/` または `ml/streaming/` に閉じ込める
- service 層から adapter を直接 import しない
- Terraform を正とする
- `make check` と必要な `make tf-*` を通す
