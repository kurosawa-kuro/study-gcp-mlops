# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このディレクトリの性質

MLOps 学習用の **7 フェーズ構成の親ディレクトリ** (Phase 7 = 到達ゴール)。  
全 phase を単一の親 Git リポジトリで管理する。フェーズを跨ぐ共通ビルド / テストは持たず、作業は常に各 phase 配下で完結する。

| Phase | ディレクトリ | テーマ | 学習の主題 |
|---|---|---|---|
| 1 | `1/study-ml-foundations/` | カリフォルニア住宅価格予測 | ML 基礎（学習・評価・保存） |
| 2 | `2/study-ml-app-pipeline/` | App + Pipeline + Port/Adapter | FastAPI / DI / core-ports-adapters 構成 |
| 3 | `3/study-hybrid-search-local/` | 不動産検索 (Local) | ハイブリッド検索 + Port/Adapter (Meilisearch + PostgreSQL + Redis + multilingual-e5) |
| 4 | `4/study-hybrid-search-gcp/` | 不動産検索 (GCP) | GCP マネージドサービス化 (Meilisearch on Cloud Run + BigQuery `VECTOR_SEARCH` + Terraform + WIF) |
| 5 | `5/study-hybrid-search-vertex/` | 不動産検索 (Vertex AI) | Vertex AI プリミティブ化 (Pipelines / **Feature Store + Feature Group + Feature Online Store (training-serving skew 防止のため必須)** / **Vertex Vector Search (semantic 検索の本番 serving index、embedding 生成履歴・メタデータは BigQuery 側に保持)** / Model Registry / Monitoring v2)。Phase 4 の BigQuery `VECTOR_SEARCH` 経路を Vertex Vector Search に置換 |
| 6 | `6/study-hybrid-search-pmle/` | GCP PMLE 試験範囲の実統合 | **Phase 5 完成系に PMLE 追加技術を adapter / 副経路 / 追加エンドポイント / 追加 Terraform として実統合** (BQML / Dataflow / Explainable AI / Monitoring SLO / Scheduled Query 等)。Feature Store / Vertex Vector Search は Phase 5 から継承(本 Phase では Dataflow / Scheduled Query で feature 入力生成・更新を強化)。不変は「不動産ハイブリッド検索というテーマとその中核コード」のみ |
| 7 | `7/study-hybrid-search-gke/` | 不動産検索 (GKE + KServe, 到達ゴール) | **Phase 6 の serving 層のみ** を GKE Deployment + KServe InferenceService に差し替え (Pipelines / **Vertex AI Feature Store + Feature Group + Feature Online Store** / **Vertex Vector Search** / Model Registry / BigQuery / Meilisearch は Phase 6 から継承。Feature Online Store は Phase 5 構築済を KServe から opt-in 参照) |

Phase 1 -> 2 は「学習基礎」と「アプリ・設計パターン」を分離し、Phase 3 以降で検索ドメインに展開する。Phase 6 は実装を前進させるのではなく「Phase 5 実コードに PMLE 技術を統合して動かす」フェーズ。Phase 7 は **到達ゴール**で、Phase 6 の serving 層のみを GKE + KServe に差し替える。詳細は `README.md` を参照。

Phase 間でコードは共有しないが、**設計思想（Port/Adapter、`core -> ports <- adapters` の依存方向）は一貫**させ、adapter 実装だけ差し替えていく — これが phase を跨ぐ変更を判断するときの軸。複数 phase に同名の概念があっても、**実装 (adapter) の差し替えだけで済むか、思想 (port / core) 自体に触れるのかを必ず区別する**。

## 非負制約（Phase 3/4/5/6/7 共通）

- ハイブリッド検索の中核 **5 要素** を必須とする: **Meilisearch BM25 + multilingual-e5 + ベクトルストア (Phase 4 = BigQuery `VECTOR_SEARCH` / Phase 5+ = Vertex AI Vector Search) + RRF + LightGBM LambdaRank**
- この 5 要素を削除・置換・無効化する変更は、明示的な user 合意がない限り実施しない
- **Vertex Vector Search の役割 (Phase 5+)**: ME5 ベクトル検索の本番 serving index。embedding 生成履歴・メタデータの正本は BigQuery 側に置き続ける (data lake / serving index の二層構造)
- **Feature Store (Phase 5 必須)**: Vertex AI Feature Store + Feature Group + Feature Online Store により training-serving skew を防ぐ。Phase 4 で BQ feature table / view の土台を作り、Phase 5 で格上げ。Phase 6 では Dataflow / Scheduled Query で更新パイプラインを強化、Phase 7 では KServe から Feature Online Store を opt-in 参照
- **実案件 reference architecture**: Elasticsearch + Redis 同義語辞書 + ME5 + Vertex Vector Search + LightGBM (詳細は [`5/study-hybrid-search-vertex/docs/01_仕様と設計.md` §「実案件想定の reference architecture」](5/study-hybrid-search-vertex/docs/01_仕様と設計.md))。本リポは Meilisearch + Redis cache を **学習用 substitute** として据え置く。Port/Adapter で `MeilisearchAdapter` ↔ `ElasticsearchAdapter` の差し替えで到達可能な構造を維持。**Meilisearch を Elasticsearch に置換するのは user 合意必須**
- Phase 6 では **中核コード (`/search` デフォルト挙動) は絶対に変えない**。それ以外は PMLE 学習のため積極的に改変してよい (新 Port / Adapter / 新エンドポイント / 新 pipeline / 新 Terraform モジュール / feature flag 追加)

## 最重要ルール — 必ず phase 配下の CLAUDE.md を読む

作業対象フェーズが分かった時点で、**その phase 配下の `CLAUDE.md` を最優先で読む**。各 phase の CLAUDE.md には:

- 非負制約 (GCP プロジェクト / リージョン / Python / パッケージ管理等、User 確認無しに変えてはいけない項目)
- feature parity invariant (同一 PR で揃えるべき複数ファイル)
- `make` ターゲット一覧 + 実行順序
- ドキュメント衝突時の権威順位
- その phase 特有の「紛らわしい点」

が載っており、本ファイルの抽象的な説明より優先する。特に Phase 4 / 5 / 6 の CLAUDE.md は設計テーゼ / 非負制約 / parity invariant を載せた load-bearing なドキュメント。Phase 6 の CLAUDE.md には「中核コード以外は PMLE 学習のため自由に改変してよい」「labs/ 隔離 NG」の原則も明記されている。

親は単一 Git リポだが、各 phase は独立 Python 環境・独立 Makefile なので、**他 phase のコマンドや設計慣行をそのまま持ち込まない** (例: Phase 1 は Docker Compose + `make all`、Phase 4/5/6 は `uv` + `make sync && make check`)。

## 実行方式の段差（学習設計）

- Phase 1/2: Docker Compose 中心（ローカルで工程を理解）
- Phase 3: `uv` + Docker Compose 併用
- Phase 4/5: クラウド実行基盤中心（Cloud Run / BigQuery / Vertex AI）。Phase 4 で BQ feature table / view の土台を作り、Phase 5 で Feature Store + Vertex Vector Search に格上げ
- Phase 6: Phase 5 完成系 + PMLE 追加技術統合 (BQML / Dataflow / Explainable AI / Monitoring SLO 等)。Feature Store と Vertex Vector Search は Phase 5 から継承
- Phase 7 (到達ゴール): GKE + KServe serving (学習側は Phase 5/6 の Vertex AI Pipelines + Vertex Vector Search + Feature Store を継承)。KServe から Feature Online Store を opt-in 参照する経路を追加

この段差は、設計思想を維持したまま実行基盤を段階的に差し替えるためのもの。Phase 6 は基盤を差し替えるのではなく「同じ基盤に追加技術を adapter / 副経路として統合する」のが特徴。

## フェーズ横断の原則

- **phase 選択**: ユーザ指定がなければ、変更対象ファイルの phase のルールに従う。ファイルが特定できない場合は確認する
- **phase 跨ぎの変更**: 全 phase を触るリファクタや機械的移行以外では、複数 phase を同時に変更しない。同じ概念名でも実装が違うことが多い
- **`OLD-study-gcp-mlops-hybrid-search-vertex/` / `study-gcp-mlops-pmle/`** — アーカイブ。参考資料として読むのは可、修正は User の明示指示がない限り触らない
- **トップレベルの日本語 md** (`ランキング最適化ロジック.md` / `簡易代替技術.md` / `類似テーマ.md`) は設計メモ・アイデアストック。コード側との整合は保証されない

## コマンド早見

phase ごとに設計思想が違うので、`make help` を最初に叩く:

```bash
cd 1/study-ml-foundations && make               # Docker Compose 系: build/seed/train/test (serve なし)
cd 2/study-ml-app-pipeline && make              # Docker Compose 系: build/seed/train/serve/test
cd 3/study-hybrid-search-local && make help     # ops-bootstrap / ops-daily / ops-weekly 系 (Docker Compose)
cd 4/study-hybrid-search-gcp && make help     # uv + Terraform + Cloud Run 系 (make check が CI 同等)
cd 5/study-hybrid-search-vertex && make help    # Phase 4 継承 + Vertex AI
cd 6/study-hybrid-search-pmle && make help    # Phase 5 継承 + PMLE 4 技術統合 (BQML / Dataflow / Explainable AI / Monitoring SLO) + Feature Store 入力強化 (+ ops-slo-status / bqml-train-popularity / enrich-properties)
cd 7/study-hybrid-search-gke && make help       # Phase 6 継承 + GKE + KServe (到達ゴール)
```

Phase 4 / 5 / 6 / 7 はローカル CI 同等チェックとして `make check` (ruff + ruff format --check + mypy strict + pytest) があり、変更後はこれを走らせる。Phase 1 / 2 は `make test` (pytest のみ)、Phase 3 は `make test` + `make check-layers` + `make verify-pipeline`。

## 参照リポジトリ (Phase 4 / 5 が継承元として挙げるもの)

- `/home/ubuntu/repos/study-gcp-mlops/study-llm-reranking-mlops` — 不動産ハイブリッド検索設計 (LambdaRank / NDCG / ME5)
- `/home/ubuntu/repos/starter-kit/mlops/` — GCP I/O 層 (GCS / BQ insert / Cloud Logging)
- `/home/ubuntu/repos/study-gcp/study-gcp-mlops/` — Terraform + CI/CD 雛形

これらは本リポ外なので、パスが実在するかは必要時に確認する。

## エージェント

`.github/agents/gcp-mlops-theme-research.agent.md` — 検索/ランキングアーキテクチャの比較と日本語マークダウン提案専用エージェント。コード変更やシェル実行は行わず、markdown の設計メモを書くための user-invocable agent。
