# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このディレクトリの性質

MLOps 学習用の **5 フェーズ構成の親ディレクトリ**。  
全 phase を単一の親 Git リポジトリで管理する。フェーズを跨ぐ共通ビルド / テストは持たず、作業は常に各 phase 配下で完結する。

| Phase | ディレクトリ | テーマ | 学習の主題 |
|---|---|---|---|
| 1 | `1/study-ml-foundations/` | カリフォルニア住宅価格予測 | ML 基礎（学習・評価・保存） |
| 2 | `2/study-ml-app-pipeline/` | App + Pipeline + Port/Adapter | FastAPI / DI / core-ports-adapters 構成 |
| 3 | `3/study-hybrid-search-local/` | 不動産検索 (Local) | ハイブリッド検索 + Port/Adapter (Meilisearch + PostgreSQL + Redis + multilingual-e5) |
| 4 | `4/study-hybrid-search-cloud/` | 不動産検索 (GCP) | Cloud Native 化 (Meilisearch on Cloud Run + BigQuery `VECTOR_SEARCH` + Terraform + WIF) |
| 5 | `5/study-hybrid-search-vertex/` | 不動産検索 (Vertex AI) | Vertex AI プリミティブ化 (Pipelines / Feature Store / Vector Search / Model Registry / Monitoring v2) |

Phase 1 -> 2 は「学習基礎」と「アプリ・設計パターン」を分離し、Phase 3 以降で検索ドメインに展開する。詳細は `README.md` を参照。

## 最重要ルール — 必ず phase 配下の CLAUDE.md を読む

作業対象フェーズが分かった時点で、**その phase 配下の `CLAUDE.md` を最優先で読む**。各 phase の CLAUDE.md には:

- 非負制約 (GCP プロジェクト / リージョン / Python / パッケージ管理等、User 確認無しに変えてはいけない項目)
- feature parity invariant (同一 PR で揃えるべき複数ファイル)
- `make` ターゲット一覧 + 実行順序
- ドキュメント衝突時の権威順位
- その phase 特有の「紛らわしい点」

が載っており、本ファイルの抽象的な説明より優先する。特に Phase 4 / 5 の CLAUDE.md は設計テーゼ / 非負制約 / parity invariant を載せた load-bearing なドキュメント。

親は単一 Git リポだが、各 phase は独立 Python 環境・独立 Makefile なので、**他 phase のコマンドや設計慣行をそのまま持ち込まない** (例: Phase 1 は Docker Compose + `make all`、Phase 4/5 は `uv` workspace + `make sync && make check`)。

## 実行方式の段差（学習設計）

- Phase 1/2: Docker Compose 中心（ローカルで工程を理解）
- Phase 3: `uv` + Docker Compose 併用
- Phase 4/5: クラウド実行基盤中心（Cloud Run / BigQuery / Vertex AI）

この段差は、設計思想を維持したまま実行基盤を段階的に差し替えるためのもの。

## フェーズ横断の原則

- **phase 選択**: ユーザ指定がなければ、変更対象ファイルの phase のルールに従う。ファイルが特定できない場合は確認する
- **phase 跨ぎの変更**: 全 phase を触るリファクタや機械的移行以外では、複数 phase を同時に変更しない。同じ概念名でも実装が違うことが多い
- **`OLD-study-gcp-mlops-hybrid-search-vertex/` / `study-gcp-mlops-pmle/`** — アーカイブ。参考資料として読むのは可、修正は User の明示指示がない限り触らない
- **トップレベルの日本語 md** (`ランキング最適化ロジック.md` / `簡易代替技術.md` / `類似テーマ.md`) は設計メモ・アイデアストック。コード側との整合は保証されない

## コマンド早見

phase ごとに設計思想が違うので、`make help` を最初に叩く:

```bash
cd 1/study-ml-foundations && make             # Docker Compose 系: build/seed/train/serve/test
cd 3/study-hybrid-search-local && make help   # ops-bootstrap / ops-daily / ops-weekly 系 (Docker Compose)
cd 4/study-hybrid-search-cloud && make help   # uv + Terraform + Cloud Run 系 (make check が CI 同等)
cd 5/study-hybrid-search-vertex && make help  # Phase 4 継承 + Vertex AI
```

Phase 4 / 5 はローカル CI 同等チェックとして `make check` (ruff + ruff format --check + mypy strict + pytest) があり、変更後はこれを走らせる。Phase 1 は `make test` (pytest のみ)、Phase 3 は `make test` + `make check-layers` + `make verify-pipeline`。

## 参照リポジトリ (Phase 4 / 5 が継承元として挙げるもの)

- `/home/ubuntu/repos/study-gcp-mlops/study-llm-reranking-mlops` — 不動産ハイブリッド検索設計 (LambdaRank / NDCG / ME5)
- `/home/ubuntu/repos/starter-kit/mlops/` — GCP I/O 層 (GCS / BQ insert / Cloud Logging)
- `/home/ubuntu/repos/study-gcp/study-gcp-mlops/` — Terraform + CI/CD 雛形

これらは本リポ外なので、パスが実在するかは必要時に確認する。

## エージェント

`.github/agents/gcp-mlops-theme-research.agent.md` — 検索/ランキングアーキテクチャの比較と日本語マークダウン提案専用エージェント。コード変更やシェル実行は行わず、markdown の設計メモを書くための user-invocable agent。
