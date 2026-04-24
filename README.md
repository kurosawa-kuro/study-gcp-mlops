# study-gcp-mlops

MLOps 学習用の 6 フェーズ構成リポジトリ（+ Optional Phase 7）。  
**全フェーズを単一の親 Git リポジトリで管理**し、Phase ごとに学習対象を段階的に広げる。

---

## 全体方針

- Phase 1 は **ML 基礎に集中**（学習・評価・保存）
- Phase 2 は **App / Pipeline / Port-Adapter** を導入
- Phase 3-5 は不動産検索ドメインで **Local -> GCP -> Vertex AI** へ展開
- Phase 6 は **Phase 5 と同じ不動産ハイブリッド検索ドメインを題材として維持**し、PMLE 試験範囲の追加技術 (BQML / Dataflow / Vertex Vector Search / Monitoring SLO / Gemini RAG / Agent Builder。補助: Explainable AI / Vizier / Feature Group / Model Garden) を Phase 5 実コードに **adapter / 副経路 / 追加エンドポイント / 追加 Terraform** として統合して動くコードとして学ぶ。不変は「題材 + ハイブリッド検索中核コード (`/search` default 挙動)」のみ、それ以外は学習のため自由に改変してよい
- Phase 7 は **Optional / Advanced**。**Phase 6 の serving 層のみを GKE + KServe に置き換える Draft**（Pipelines / Feature Group / Model Registry / BigQuery / Meilisearch 等は Phase 6 から継承）
- Phase 3/4/5/6/7 は **LightGBM + multilingual-e5 + Meilisearch のハイブリッド構成を必須** とする
- Phase 間のコードは原則共有しない（教材としての独立性を優先）
- 各 Phase の正本は phase 配下ドキュメント（ルート README は全体ナビゲーション）
- ただし **設計思想（Port/Adapter、core-ports-adapters 層構造、依存方向）は一貫**させ、**adapter 実装だけ差し替える** のが本リポジトリの軸
- **W&B / Looker Studio / Doppler は教材対象外**（2026-04-24 決定）。実験履歴は Phase 1-3 で `runs/{run_id}/` + JSON/CSV metrics + git commit hash、Phase 4 以降で GCS / BigQuery / Vertex Model Registry / Vertex Pipelines Metadata へ段階移行
- **Secret Manager は Phase 4 で必須習得技術**。題材は Meilisearch master key（Phase 4-7 横断で使える実在の秘匿情報）。Secret 作成 → SA IAM bind → Cloud Run `--set-secrets` 注入 → pydantic-settings 読み取りの 4 段を踏む

---

## Phase 一覧

各 Phase の「実行方式」は表に集約し、重複説明は省く。

| Phase | ディレクトリ | テーマ | 主な学習ポイント | 主な技術 | 実行方式 |
|---|---|---|---|---|---|
| 1 | `1/study-ml-foundations/` | ML 基礎（回帰） | preprocess / feature engineering / training / evaluation / artifact 出力（model.pkl / metrics.json / params.yaml / `runs/{run_id}/`） | LightGBM, PostgreSQL | Docker Compose |
| 2 | `2/study-ml-app-pipeline/` | App + Pipeline + Port/Adapter | FastAPI lifespan DI, `core -> ports <- adapters`, predictor 経由推論、seed/train/predict job 分離 | FastAPI, LightGBM, PostgreSQL | Docker Compose |
| 3 | `3/study-hybrid-search-local/` | 不動産ハイブリッド検索（Local） | lexical + semantic + rerank、LambdaRank、Port/Adapter 実践 | Meilisearch, multilingual-e5, LightGBM LambdaRank, Redis | uv + Docker Compose |
| 4 | `4/study-hybrid-search-cloud/` | 不動産ハイブリッド検索（GCP） | GCP マネージドサービス化、RRF、再学習ループ、IaC/CI、**Secret Manager → Cloud Run secret injection（必須習得）** | Cloud Run, GCS, BigQuery, Cloud Logging, **Secret Manager**, Terraform, WIF | uv + クラウド実行基盤 |
| 5 | `5/study-hybrid-search-vertex/` | Vertex AI 標準 MLOps 差分移行 | Vertex Pipelines / Endpoint / Model Registry / Monitoring への adapter 差し替え | Vertex AI, Vertex Pipelines, Endpoint, Model Registry, Monitoring | uv + Vertex AI |
| 6 | `6/study-gcp-ml-engineer-cert/` | GCP PMLE 追加技術ラボ (Phase 5 実コードへ統合、2026-04-24 全 8 完了) | PMLE 範囲の追加技術を adapter / 副経路 / 追加エンドポイント / Terraform として統合。default flag では Phase 5 挙動維持。不変はハイブリッド検索中核 (`/search` default) のみ | BQML / Dataflow / Vertex Vector Search / Monitoring SLO / Gemini RAG / Agent Builder（補助: Explainable AI / Vizier / Feature Group / Model Garden） | uv + Vertex AI + Terraform |
| 7 | `7/study-hybrid-search-gke/` | GKE/KServe 差分移行（Draft） | Phase 6 の serving 層のみを GKE + KServe へ置換（Pipelines / Feature Group / Model Registry / BigQuery / Meilisearch は Phase 6 から継承） | GKE, KServe, Gateway API, Workload Identity | uv + GKE/KServe |

実行方式の段差は「同じ設計思想を維持し、実行基盤だけ段階的に置き換える」ための学習設計。

### Phase 2 → 3 の接続（飛躍を埋める短い説明）

Phase 2 で学んだ **Port/Adapter を、より複雑なドメインで実践する** のが Phase 3。具体的には:

- ドメインが 回帰（単発予測）→ **検索（lexical + semantic + rerank の多段構成）** になる
- ML タスクが 回帰 → **ランキング学習（LambdaRank / NDCG）** になる
- Adapter が増える: Meilisearch（BM25）、multilingual-e5（Embedding）、Redis（キャッシュ）
- 「同じ Port 抽象に、複数 adapter を差し込む」のが Phase 3 で初めて本格化する

設計思想は Phase 2 と同じだが、**ドメイン複雑度と adapter 数が一段上がる** と捉えるとスムーズ。

### Phase 3-6 / 7 の非負制約（必須）

- ハイブリッド検索の基盤は **LightGBM + multilingual-e5 + Meilisearch** を維持する
- 検索品質改善は「この 3 要素を前提にした上で」実施する
- 置換・削減・無効化を行う場合は、事前に明示的な合意を必要とする
- Phase 7 は **Phase 6** の学習/データ基盤をそのまま継承し、serving 層のみ差し替える

### Phase 6 の非負制約（必須）

- **題材は Phase 5 と同じ不動産ハイブリッド検索ドメインを維持する**（PMLE 試験がケーススタディ形式であること、Phase 3-5 の設計思想との一貫性、Responsible AI / GenAI の実題材化が理由）
- **ハイブリッド検索中核コード (Meilisearch BM25 + BQ `VECTOR_SEARCH` + multilingual-e5 + RRF + LightGBM LambdaRank) の挙動は絶対に変えない**（親リポ非負制約「LightGBM + multilingual-e5 + Meilisearch」の継承）
- **中核以外の改変は PMLE 学習のため自由に行う**。新 Port / Adapter / Service / Endpoint / KFP component / Terraform モジュール / parity 6 ファイル同 PR 更新などを積極的に使って試験範囲 8 技術を実コードに統合する
- **default feature flag では Phase 5 挙動を維持**（新技術は opt-in で有効化）
- **`make check` / parity invariant / Port/Adapter 境界検知 / WIF** は Phase 6 追加コードも含めて継続して PASS させる
- 中核コードを変える提案 (Meilisearch 置換 / LambdaRank 置換 / RRF 廃止 等) は事前に明示的な合意を必要とする

---

## 全 Phase 共通ツール（横断的に登場）

Phase 表には各 Phase で**新規に登場する**技術を載せる。次のツールは Phase を跨いで継続利用するため、ここに切り出す。

| ツール | 役割 | 初登場 | 本格活用 |
|---|---|---|---|
| JSON / CSV metrics | ローカル評価結果・run 履歴保存 | Phase 1 | Phase 1-3 |
| Git commit hash | 再現性管理 | Phase 1 | 全 Phase |
| pytest | 全 Phase 共通のテストランナー | Phase 1 | 全 Phase |
| Git | 親リポで全 Phase を単一管理 | リポジトリ開始時点 | 全 Phase |
| pydantic-settings (YAML) | 設定とシークレットの分離 | Phase 1 | 全 Phase |
| Docker / Docker Compose | ローカル実行基盤 | Phase 1 | Phase 1–3 |
| uv | Python 依存管理 | Phase 3 | Phase 3–7 |

GCP 周辺（WIF, Cloud Run, Vertex AI, Secret Manager 等）は Phase 4 以降に集中するため、Phase 表に残す。W&B / Looker Studio / Doppler は 2026-04-24 に教材対象外化済。

---

## まずどこから始めるか

### 学習順（推奨）

1. `1/study-ml-foundations`
2. `2/study-ml-app-pipeline`
3. `3/study-hybrid-search-local`
4. `4/study-hybrid-search-cloud`
5. `5/study-hybrid-search-vertex`
6. `6/study-gcp-ml-engineer-cert`
7. `7/study-hybrid-search-gke`（Optional / Advanced、Draft）

### 目的別ショートカット（前提 Phase を併記）

- **ML 基礎だけ学ぶ**: Phase 1（前提なし）
- **設計パターン（Port/Adapter）を学ぶ**: Phase 2, 3（前提: **Phase 1 相当の ML 基礎知識**）
- **GCP MLOps の運用全体**: Phase 4（前提: **Phase 3 の Port/Adapter 理解**）
- **Vertex AI への移行差分**: Phase 5（前提: **Phase 4 の GCP 構成理解**）
- **GCP ML Engineer 認定相当の総仕上げ**: Phase 6（前提: **Phase 4/5 の GCP / Vertex 構成理解**。PMLE 試験範囲の 8 技術を Phase 5 実コードに adapter / 新規コンポーネントとして統合して学ぶ。不変はハイブリッド検索中核のみ）
- **GKE/KServe への serving 差分移行（Optional/Advanced, Draft）**: Phase 7（前提: **Phase 5 の Vertex 構成理解** + Kubernetes 基礎）

---

## 学習運用フロー（成果物・評価・ログの置き場）

Phase ごとに成果物・評価結果・実行履歴の置き場を段階移行させる。詳細は phase 配下ドキュメントが正本。

### Phase 1〜3（ローカル成果物）

```text
model.pkl
metrics.json
params.yaml
runs/20260424_001/
```

- metric 保存: JSON / CSV
- model 保存: local filesystem
- 実験履歴: run_id 付きディレクトリ
- 再現性: `config.yaml` + git commit hash

### Phase 4（GCP Serverless）

- モデル成果物: GCS（`gs://<project>-models/` 配下に `models/` / `reports/` / `artifacts/`）
- 評価結果: BigQuery table
- 実行ログ: Cloud Logging
- 監視: Cloud Monitoring
- CI/CD: GitHub Actions + WIF
- IaC: Terraform
- **Secret Manager（必須習得）**: `meili-master-key` container + SA IAM bind + Cloud Run `--set-secrets=MEILI_MASTER_KEY=meili-master-key:latest` 注入 + app 側 pydantic-settings 読み取り

### Phase 5（Vertex AI 標準）

- モデル正本: Vertex Model Registry（昇格運用）
- Pipeline 履歴: Vertex AI Pipelines / Metadata（lineage）
- 推論: Vertex Endpoint（deploy history）
- モデル監視: Vertex AI Model Monitoring

### Phase 6（Phase 5 継承 + PMLE 追加技術ラボ）

- Phase 5 の運用面をそのまま継承
- 追加技術は adapter / 副経路 / 追加エンドポイント / 追加 Terraform モジュールとして実装し、default flag では Phase 5 挙動を維持

### Phase 7（Optional / Advanced, Draft）

- Phase 6 から学習/データ基盤を継承
- serving 層のみ GKE + KServe に差し替え。Meilisearch master key は GKE 側では Kubernetes Secret 手動同期で注入（External Secrets Operator 導入は未着手）

---

## 分割後の重要な変更点（Phase 1 -> 2）

- Phase 1 から `app/` と推論系を分離し、学習基礎フェーズに限定
- Phase 2 を新設し、API・DI・Port/Adapter・job 分離を導入
- Phase 1 と Phase 2 は独立運用（import 共有しない）
- モデル成果物の共有はしない前提（Phase 2 は Phase 2 内で学習して自己完結）

---

## リポジトリ構成（ルート）

```text
study-gcp-mlops/
├── 1/study-ml-foundations/
├── 2/study-ml-app-pipeline/
├── 3/study-hybrid-search-local/
├── 4/study-hybrid-search-cloud/
├── 5/study-hybrid-search-vertex/
├── 6/study-gcp-ml-engineer-cert/
├── 7/study-hybrid-search-gke/   # Optional / Advanced (Draft)
└── docs/
```

---

## 主要ドキュメント

### 正本仕様（Phase-local が最優先）

- 各 Phase 配下の `README.md` / `CLAUDE.md` / `docs/` — その Phase の実態を正とする（最優先）

### 全体横断

- `docs/05_Docker配置規約.md` — Dockerfile 配置・命名ルール（Phase を跨いで一貫）
- `docs/README.md` — ルート docs の入口と参照優先順位
- `docs/01_仕様と設計.md` — Phase 1〜7 の仕様設計ハブ
- `docs/03_実装カタログ.md` — Phase 1〜7 の実装カタログハブ
- `docs/04_運用.md` — Phase 1〜7 の運用ハブ
- `docs/phase調整案.md` — W&B / Looker Studio / Doppler 削除と Secret Manager (Meilisearch master key) への転用計画（2026-04-24 一括適用済）
- `docs/phases/README.md` — Phase 別 docs 入口

### docs ハブ関連付け（入口の対応）

- トップ入口: `README.md` (本ファイル)
- 横断入口: `docs/README.md`
- 仕様ハブ: `docs/01_仕様と設計.md`
- 実装ハブ: `docs/03_実装カタログ.md`
- 運用ハブ: `docs/04_運用.md`
- Phase 別入口: `docs/phases/README.md`
- Phase 個別入口:
  - `docs/phases/phase1/README.md`
  - `docs/phases/phase2/README.md`
  - `docs/phases/phase3/README.md`
  - `docs/phases/phase4/README.md`
  - `docs/phases/phase5/README.md`
  - `6/study-gcp-ml-engineer-cert/README.md`（PMLE 8 技術を Phase 5 実コードに実統合、2026-04-24 完了）
  - `6/study-gcp-ml-engineer-cert/docs/01_仕様と設計.md`（統合トピック詳細 + ファイル配置図）
  - `6/study-gcp-ml-engineer-cert/docs/02_移行ロードマップ.md`（決定的仕様、8 トピック全完）
  - `7/study-hybrid-search-gke/docs/02_移行ロードマップ.md`（Optional / Advanced, Draft）

### 過去の設計判断ログ（archive）

- `docs/archive/` — 完了済み作業の履歴・判断ログを保管
- `docs/archive/README.md` — archive 運用ルール

---

## 運用ルール（共通）

- 変更は原則 Phase 単位で閉じる
- 学習用途のため、重複コードは許容（意図的複製）
- Phase を跨ぐ共有ライブラリ化は優先しない
- ドキュメントは「現行フェーズの実態」を最優先で更新する

---

## ドメイン選定の経緯

構想段階では社内規定検索・商品検索など複数ドメイン案があったが、Phase 3 以降は **不動産検索ドメインに統一** した。Phase 6 も Phase 5 からドメインを引き継ぐ（PMLE 認定勉強のための独立ドメインは作らない）。

統一理由:

- **lexical（キーワード / フィルタ）と semantic（意味類似）の両方が効くタスク** であり、ハイブリッド検索の教材として自然
- **ランキング学習（行動ログ → LambdaRank）の題材として適切な複雑さ** を持つ
- Phase 2 → 3 → 4 → 5 の移植の学びに集中するため、**ドメインを動かさず実行基盤だけ置き換える** 構成にしたかった
- Phase 6 (PMLE 総仕上げ) でも **Phase 5 実装を動くコードとして使い、そこに新技術を adapter / 新規コンポーネントとして統合する** 方が、抽象トピック暗記より試験対策として有利。Responsible AI (Explainable AI) を reranker endpoint に attach する、RAG を既存ハイブリッド検索の retrieval 層の上に bolt-on する、といった実装を通じて PMLE 試験範囲の判断軸を手を動かして身につける

学習者が「モデル課題」ではなく **「設計と移行差分」** を追える構成を重視している。

---

## 技術選定の補足

### 検索エンジン（Phase 3 以降）: Meilisearch

実務（特に大規模本番環境）では **Elasticsearch / OpenSearch** が採用される場面が多いが、本リポジトリでは Meilisearch を採用する:

- **学習目的では Meilisearch で十分** — BM25 全文検索 + 構造化フィルタ（`city` / `price_lte` / `walk_min` 等）という本リポの要件を素直にカバーできる
- **セットアップコストが低い** — 単一バイナリ・軽量 Docker image・チューニング項目が少ないため、**学習関心事（Port/Adapter、semantic 統合、RRF、rerank）に集中できる**
- **adapter 差し替えで Elasticsearch へ切り替え可能** — Phase 3 で lexical 層を Port/Adapter の背後に隠しているため、**本番想定では `MeilisearchAdapter` を `ElasticsearchAdapter` に差し替えるだけ** で切り替え可能（= 本リポジトリの軸「設計思想は一貫、adapter だけ差し替え」の具体例）

他の選定（LightGBM / multilingual-e5 / Redis / BigQuery VECTOR_SEARCH 等）は各 Phase の CLAUDE.md / README に理由を記載。
