# study-gcp-mlops

MLOps 学習用の 5 フェーズ構成リポジトリ。  
**全フェーズを単一の親 Git リポジトリで管理**し、Phase ごとに学習対象を段階的に広げる。

---

## 全体方針

- Phase 1 は **ML 基礎に集中**（学習・評価・保存）
- Phase 2 は **App / Pipeline / Port-Adapter** を導入
- Phase 3 以降は不動産検索ドメインで **Local -> GCP -> Vertex AI** へ展開
- Phase 3/4/5 は **LightGBM + multilingual-e5 + Meilisearch のハイブリッド構成を必須** とする
- Phase 間のコードは原則共有しない（教材としての独立性を優先）
- 各 Phase の正本は phase 配下ドキュメント（ルート README は全体ナビゲーション）
- ただし **設計思想（Port/Adapter、core-ports-adapters 層構造、依存方向）は一貫**させ、**adapter 実装だけ差し替える** のが本リポジトリの軸

---

## Phase 一覧

各 Phase の「実行方式」は表に集約し、重複説明は省く。

| Phase | ディレクトリ | テーマ | 主な学習ポイント | 主な技術 | 実行方式 |
|---|---|---|---|---|---|
| 1 | `1/study-ml-foundations/` | ML 基礎（回帰） | preprocess / feature engineering / training / evaluation / artifact 管理 | LightGBM, PostgreSQL | Docker Compose |
| 2 | `2/study-ml-app-pipeline/` | App + Pipeline + Port/Adapter | FastAPI lifespan DI, `core -> ports <- adapters`, predictor 経由推論、seed/train/predict job 分離 | FastAPI, LightGBM, PostgreSQL | Docker Compose |
| 3 | `3/study-hybrid-search-local/` | 不動産ハイブリッド検索（Local） | lexical + semantic + rerank、LambdaRank、Port/Adapter 実践 | Meilisearch, multilingual-e5, LightGBM LambdaRank, Redis | uv + Docker Compose |
| 4 | `4/study-hybrid-search-cloud/` | 不動産ハイブリッド検索（GCP） | Cloud Native 化、RRF、再学習ループ、IaC/CI | Cloud Run, BigQuery, Dataform, Terraform, WIF | uv + クラウド実行基盤 |
| 5 | `5/study-hybrid-search-vertex/` | Vertex AI 差分移行 | Vertex Pipelines/Endpoints/Registry/Monitoring への adapter 差し替え | Vertex AI, KFP, Endpoint, Feature Group, Vizier | uv + Vertex AI |

実行方式の段差は「同じ設計思想を維持し、実行基盤だけ段階的に置き換える」ための学習設計。

### Phase 2 → 3 の接続（飛躍を埋める短い説明）

Phase 2 で学んだ **Port/Adapter を、より複雑なドメインで実践する** のが Phase 3。具体的には:

- ドメインが 回帰（単発予測）→ **検索（lexical + semantic + rerank の多段構成）** になる
- ML タスクが 回帰 → **ランキング学習（LambdaRank / NDCG）** になる
- Adapter が増える: Meilisearch（BM25）、multilingual-e5（Embedding）、Redis（キャッシュ）
- 「同じ Port 抽象に、複数 adapter を差し込む」のが Phase 3 で初めて本格化する

設計思想は Phase 2 と同じだが、**ドメイン複雑度と adapter 数が一段上がる** と捉えるとスムーズ。

### Phase 3-5 の非負制約（必須）

- ハイブリッド検索の基盤は **LightGBM + multilingual-e5 + Meilisearch** を維持する
- 検索品質改善は「この 3 要素を前提にした上で」実施する
- 置換・削減・無効化を行う場合は、事前に明示的な合意を必要とする

---

## 全 Phase 共通ツール（横断的に登場）

Phase 表には各 Phase で**新規に登場する**技術を載せる。次のツールは Phase を跨いで継続利用するため、ここに切り出す。

| ツール | 役割 | 初登場 | 本格活用 |
|---|---|---|---|
| W&B | 実験管理（metrics / artifact tracking） | Phase 1 | Phase 1 以降 |
| pytest | 全 Phase 共通のテストランナー | Phase 1 | 全 Phase |
| Git | 親リポで全 Phase を単一管理 | リポジトリ開始時点 | 全 Phase |
| pydantic-settings (YAML) | 設定とシークレットの分離 | Phase 1 | 全 Phase |
| Docker / Docker Compose | ローカル実行基盤 | Phase 1 | Phase 1–3 |
| uv | Python 依存管理 | Phase 3 | Phase 3–5 |

GCP 周辺（WIF, Dataform, Cloud Run, Vertex AI, Secret Manager 等）は Phase 4 以降に集中するため、Phase 表に残す。

---

## まずどこから始めるか

### 学習順（推奨）

1. `1/study-ml-foundations`
2. `2/study-ml-app-pipeline`
3. `3/study-hybrid-search-local`
4. `4/study-hybrid-search-cloud`
5. `5/study-hybrid-search-vertex`

### 目的別ショートカット（前提 Phase を併記）

- **ML 基礎だけ学ぶ**: Phase 1（前提なし）
- **設計パターン（Port/Adapter）を学ぶ**: Phase 2, 3（前提: **Phase 1 相当の ML 基礎知識**）
- **GCP MLOps の運用全体**: Phase 4（前提: **Phase 3 の Port/Adapter 理解**）
- **Vertex AI への移行差分**: Phase 5（前提: **Phase 4 の GCP 構成理解**）

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
└── docs/
```

---

## 主要ドキュメント

### 正本仕様（Phase-local が最優先）

- 各 Phase 配下の `README.md` / `CLAUDE.md` / `docs/` — その Phase の実態を正とする（最優先）

### 全体横断

- `docs/05_Docker配置規約.md` — Dockerfile 配置・命名ルール（Phase を跨いで一貫）
- `docs/README.md` — ルート docs の入口と参照優先順位

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

構想段階では社内規定検索・商品検索など複数ドメイン案があったが、Phase 3 以降は **不動産検索ドメインに統一** した。

統一理由:

- **lexical（キーワード / フィルタ）と semantic（意味類似）の両方が効くタスク** であり、ハイブリッド検索の教材として自然
- **ランキング学習（行動ログ → LambdaRank）の題材として適切な複雑さ** を持つ
- Phase 2 → 3 → 4 → 5 の移植の学びに集中するため、**ドメインを動かさず実行基盤だけ置き換える** 構成にしたかった

学習者が「モデル課題」ではなく **「設計と移行差分」** を追える構成を重視している。
