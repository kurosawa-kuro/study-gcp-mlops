# CLAUDE.md

本リポジトリで作業する Claude Code 向けのガイド。**非負制約 / 設計テーゼ / 主要コマンド** を最優先で載せる。

ドキュメント全般の運用規約は [`docs/README.md`](docs/README.md)、スコープの決定権は [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md)、実装の逐一は [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md)。本 CLAUDE.md はそれらに従属する。

---

## 最初に読むもの (順番)

1. [`README.md`](README.md) — Phase 実装範囲 / セットアップ / 主要 make コマンド
2. [`docs/01_仕様と設計.md`](docs/01_仕様と設計.md) — 仕様の決定事項（3 段構成 / LambdaRank / 特徴量 / DB 設計 / KPI）
3. [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md) — Phase 0→6 の実装履歴と意思決定
4. [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md) — ディレクトリ / ファイル / DB テーブル / API / make ターゲット
5. [`docs/04_運用.md`](docs/04_運用.md) — セットアップ手順と日次 / 週次運用

---

## Phase 2 の設計テーゼ (題材: 不動産ハイブリッド検索 Local 版)

- **題材**: 自由文クエリ + フィルタ → 物件ランキング上位 20 件。3 段構成 = (1) Meilisearch BM25、(2) multilingual-e5 の cosine 類似度、(3) LightGBM `lambdarank` 再ランク
- **Local 完結**: WSL + Docker Compose で `postgres / pgadmin / meilisearch / redis / api` を 1 コマンド起動。クラウド・IaC は含まない
- **lexical × semantic 融合は "特徴量化" で止める**: `me5_score` を LightGBM の 1 特徴量として渡し、混ぜ方をモデルに委ねる。RRF による rank 事前融合は **Phase 3 で導入**（本 Phase ではやらない）
- **LambdaRank + NDCG**: `jobs/src/training/lgbm_trainer.py` の `objective: lambdarank` / `metric: ndcg` で検索結果の順序を最適化。`group_sizes` によるクエリ単位グルーピングが load-bearing
- **フォールバック可用性**: LightGBM モデル未配置でも `/search` は動く（`ctr*0.4 + fav_rate*0.2 + inquiry_rate*0.2 + me5_score*0.2` の重み付き和で暫定順位）
- **Port/Adapter 設計**: `common/src/common/ports/` と `pipelines/src/pipelines/adapters/` で検索エンジン / 埋め込み / reranker / キャッシュを抽象化
- **スコープ固定**: Local 検証 + 学習用ポートフォリオ。クラウド化は Phase 3 (`3/study-hybrid-search-cloud`) で実施

---

## 非負制約 (User 確認無しに変えない)

| 項目 | 値 | 理由 |
|---|---|---|
| Python | 3.11+ (開発は 3.12 想定) | requirements.txt 互換 |
| パッケージ管理 | pip + `requirements.txt` / `requirements-dev.txt` | Phase 3/4 の uv とは異なる（Local 学習用途を優先） |
| DB | PostgreSQL 16 (docker-compose `postgres` サービス) | Phase 3 では BigQuery に置換、本 Phase は保持 |
| Lexical 検索 | Meilisearch v1.7 (docker-compose `meilisearch` サービス) | BM25、Elasticsearch 非採用方針 |
| Embedding | `intfloat/multilingual-e5-base` (ME5) | `query:` / `passage:` prefix 必須 |
| Reranker 目的関数 | LightGBM `objective: lambdarank` + `metric: ndcg` + `ndcg_eval_at: [10]` | ランキング学習。回帰 (`regression_l2`) や分類には戻さない |
| キャッシュ | Redis (TTL 120 秒、graceful fallback、ヒット時はログ保存 skip) | Memorystore は本 Phase 対象外 |
| 設定値 2 分割 | `env/config/setting.yaml` (non-credential) / `env/secret/credential.yaml` (gitignored) | Phase 3/4 と共通のパターン |
| docker-compose 起動 | `scripts/setup/compose.sh` 経由（`credential.yaml` を env に export するラッパー） | 直接 `docker compose up` を叩くと `POSTGRES_PASSWORD` 未設定で起動失敗 |

---

## 開発コマンド（詳細は `Makefile` / `make help`）

| target | 用途 |
|---|---|
| `make sync` | pip install -r requirements-dev.txt（Local 環境構築） |
| `make up` / `make build` / `make down` / `make logs` | docker compose ライフサイクル（`scripts/setup/compose.sh` 経由） |
| `make ops-livez` | API ヘルスチェック（`scripts/ops/health_check.py`）|
| `make test` | pytest |
| `make check-layers` | AST で layer 依存ルール違反を検出（`scripts/checks/layers.py`） |
| `make ops-bootstrap` | 初期セットアップ一括（migrations → seed → index → 初回学習） |
| `make ops-daily` | 日次運用（search-sync / features-daily / embeddings-generate / kpi-daily） |
| `make ops-weekly` | 週次運用（eval-compare / eval-offline / eval-weekly-report / retrain-weekly） |
| `make verify-pipeline` | 代表 E2E smoke（check-layers → ops-livez → ops-search → ops-feedback → ops-ranking → ops-ranking-verbose → eval-compare → eval-offline） |
| `make ops-search` / `ops-feedback` / `ops-ranking` / `ops-ranking-verbose` | 各エンドポイント smoke（Phase 3/4 と命名揃い） |
| `make ops-label-seed` | 学習用 feedback ラベルのシード投入 |

---

## ディレクトリ構造

```
app/                  FastAPI エントリ + routes
common/               core / clients / ports / dtos
definitions/          PostgreSQL マイグレーション SQL
jobs/                 バッチジョブ / 学習
pipelines/            adapters / application / repositories / services
```

```
scripts/
├── checks/layers.py        AST で layer 依存ルール検査（Makefile check-layers）
├── setup/compose.sh        credential.yaml → env export → docker compose 起動
├── setup/rename_structure.py  ディレクトリ構成リネーム補助
└── ops/*.py                各 make ops-* target の実装
```

---

## 参照すべき他 Phase

| 役割 | パス | 引用ポイント |
|---|---|---|
| クラウド移行先 | `/home/ubuntu/repos/study-gcp-mlops/3/study-hybrid-search-cloud` | 本 Phase の検索スタックを BigQuery `VECTOR_SEARCH` + RRF + Cloud Run で再実装した後継 Phase |
| Vertex 版 | `/home/ubuntu/repos/study-gcp-mlops/4/study-hybrid-search-vertex` | Phase 3 に Vertex AI レイヤを後付けした最新 Phase |
| ML 基礎（前提講義） | `/home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations` | LightGBM 回帰・評価・推論 API の基本語彙 |

---

## リポジトリ状態

- Phase 0–6 実装済（`docs/02_移行ロードマップ.md` 参照）
- `make verify-pipeline` / `make ops-bootstrap` が代表スモーク
- LambdaRank + NDCG で実装済（`jobs/src/training/lgbm_trainer.py` の `objective: lambdarank`）
- RRF は **Phase 3 で新規登場**（本 Phase では `me5_score` を LightGBM 特徴量に入れる方式）
- `scripts/` は 2026-04-21 に lifecycle 別再分類（`checks/` / `ops/` / `setup/`）を実施
- `make` コマンド名は Phase 3/4 と整合済（`ops-livez` / `ops-search` / `ops-feedback` / `ops-ranking` / `ops-label-seed`）

---

## 紛らわしい点

- **`scripts/setup/compose.sh` は docker compose のラッパー**。直接 `docker compose` を叩くと `POSTGRES_PASSWORD` が空になり postgres コンテナが起動失敗する。必ず `make up` / `make down` / `make logs` / `make build` など Makefile ターゲット経由で使う
- **`me5_score` を直接順位に使わない**。Meilisearch のスコアも直接は使わず、両方とも LightGBM の特徴量として渡す
- **LambdaRank の `group` は `request_id`**（query 単位）。行単位の回帰とは学習構造が違う
- **Phase 3 への移行で "検索コアは不変、実装基盤だけ置換"**：設計思想は Phase 3 に引き継がれる。`02_移行ロードマップ.md` の「引き継ぐもの / 置き換えるもの」対比を参照

---

## 書き方（docs 全般のルール）

- 日本語で書く。技術用語は英語のまま（`LightGBM`, `LambdaRank`, `Booster`, `Meilisearch`, `ME5`, `RRF`）
- コマンドは `make` ターゲット優先。生 `docker compose` / `bq` / `terraform` は動的引数が必要な場合のみ
- 識別子は固有名を使う（テーブル名 / カラム名 / エンドポイント名）
- 番号付き STEP は上から叩けば成立する順序
- 推測で書かない。コマンドを書いたら実際に叩いて確認する
