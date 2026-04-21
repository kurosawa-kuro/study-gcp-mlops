# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このディレクトリの性質

MLOps 学習用の **4 フェーズ構成の親ディレクトリ**。ここ自体は Git リポジトリでは**なく**、各フェーズが独立した Git リポジトリとしてサブディレクトリに入っている。フェーズを跨ぐ共通ビルド / テストは存在しない — 作業は常にフェーズ配下で完結する。

| Phase | ディレクトリ | テーマ | 学習の主題 |
|---|---|---|---|
| 1 | `1/study-ml-foundations/` | カリフォルニア住宅価格予測 | ML 基礎 (LightGBM 回帰 / Docker Compose / PostgreSQL / FastAPI) |
| 2 | `2/study-hybrid-search-local/` | 不動産検索 (Local) | ハイブリッド検索 + Port/Adapter (Meilisearch + PostgreSQL + Redis + multilingual-e5) |
| 3 | `3/study-hybrid-search-cloud/` | 不動産検索 (GCP) | Cloud Native 化 (Meilisearch on Cloud Run + BigQuery `VECTOR_SEARCH` + Terraform + WIF) |
| 4 | `4/study-hybrid-search-vertex/` | 不動産検索 (Vertex AI) | Vertex AI プリミティブ化 (Pipelines / Feature Store / Vector Search / Model Registry / Monitoring v2) |

Phase 2 → 3 は Port/Adapter 経由で継承し、Lexical / Vector / データストアの実装を差し替えていく。詳細な技術スタック比較表は `README.md`。

## 最重要ルール — 必ず phase 配下の CLAUDE.md を読む

作業対象フェーズが分かった時点で、**その phase 配下の `CLAUDE.md` を最優先で読む**。各 phase の CLAUDE.md には:

- 非負制約 (GCP プロジェクト / リージョン / Python / パッケージ管理等、User 確認無しに変えてはいけない項目)
- feature parity invariant (同一 PR で揃えるべき複数ファイル)
- `make` ターゲット一覧 + 実行順序
- ドキュメント衝突時の権威順位
- その phase 特有の「紛らわしい点」

が載っており、本ファイルの抽象的な説明より優先する。特に Phase 3 / 4 の CLAUDE.md は設計テーゼ / 非負制約 / parity invariant を載せた load-bearing なドキュメント。

各 phase は独立 Git リポ・独立 Python 環境・独立 Makefile なので、**他 phase のコマンドや設計慣行をそのまま持ち込まない** (例: Phase 1 は Docker Compose + `make all`、Phase 3/4 は `uv` workspace + `make sync && make check`)。

## フェーズ横断の原則

- **phase 選択**: ユーザ指定がなければ、変更対象ファイルの phase のルールに従う。ファイルが特定できない場合は確認する
- **phase 跨ぎの変更**: 4 phase すべて触るリファクタや機械的移行以外では、複数 phase を同時に変更しない。同じ概念名でも実装が違うことが多い
- **`OLD-study-gcp-mlops-hybrid-search-vertex/` / `study-gcp-mlops-pmle/`** — アーカイブ。参考資料として読むのは可、修正は User の明示指示がない限り触らない
- **トップレベルの日本語 md** (`ランキング最適化ロジック.md` / `簡易代替技術.md` / `類似テーマ.md`) は設計メモ・アイデアストック。コード側との整合は保証されない

## コマンド早見

phase ごとに設計思想が違うので、`make help` を最初に叩く:

```bash
cd 1/study-ml-foundations && make             # Docker Compose 系: build/seed/train/serve/test
cd 2/study-hybrid-search-local && make help   # ops-bootstrap / ops-daily / ops-weekly 系 (Docker Compose)
cd 3/study-hybrid-search-cloud && make help   # uv + Terraform + Cloud Run 系 (make check が CI 同等)
cd 4/study-hybrid-search-vertex && make help  # Phase 3 継承 + Vertex AI
```

Phase 3 / 4 はローカル CI 同等チェックとして `make check` (ruff + ruff format --check + mypy strict + pytest) があり、変更後はこれを走らせる。Phase 1 は `make test` (pytest のみ)、Phase 2 は `make test` + `make check-layers` + `make verify-pipeline`。

## 参照リポジトリ (Phase 3 / 4 が継承元として挙げるもの)

- `/home/ubuntu/repos/study-gcp-mlops/study-llm-reranking-mlops` — 不動産ハイブリッド検索設計 (LambdaRank / NDCG / ME5)
- `/home/ubuntu/repos/starter-kit/mlops/` — GCP I/O 層 (GCS / BQ insert / Cloud Logging)
- `/home/ubuntu/repos/study-gcp/study-gcp-mlops/` — Terraform + CI/CD 雛形

これらは本リポ外なので、パスが実在するかは必要時に確認する。

## エージェント

`.github/agents/gcp-mlops-theme-research.agent.md` — 検索/ランキングアーキテクチャの比較と日本語マークダウン提案専用エージェント。コード変更やシェル実行は行わず、markdown の設計メモを書くための user-invocable agent。
