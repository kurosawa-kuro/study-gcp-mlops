# study-gcp-mlops

MLOps 学習用の 5 フェーズ構成リポジトリ。  
**全フェーズを単一の親 Git リポジトリで管理**し、Phase ごとに学習対象を段階的に広げる。

---

## 全体方針

- Phase 1 は **ML 基礎に集中**（学習・評価・保存）
- Phase 2 は **App / Pipeline / Port-Adapter** を導入
- Phase 3 以降は不動産検索ドメインで **Local -> GCP -> Vertex AI** へ展開
- Phase 間のコードは原則共有しない（教材としての独立性を優先）

---

## Phase 一覧

| Phase | ディレクトリ | テーマ | 主な学習ポイント | 主な技術 |
|---|---|---|---|---|
| 1 | `1/study-ml-foundations/` | ML 基礎（回帰） | preprocess / feature engineering / training / evaluation / artifact 管理 | LightGBM, PostgreSQL, Docker Compose, W&B |
| 2 | `2/study-ml-app-pipeline/` | App + Pipeline + Port/Adapter | FastAPI lifespan DI, `core -> ports <- adapters`, seed/train/predict job 分離 | FastAPI, LightGBM, PostgreSQL, Docker Compose |
| 3 | `3/study-hybrid-search-local/` | 不動産ハイブリッド検索（Local） | lexical + semantic + rerank、LambdaRank、Port/Adapter 実践 | Meilisearch, multilingual-e5, LightGBM LambdaRank, Redis |
| 4 | `4/study-hybrid-search-cloud/` | 不動産ハイブリッド検索（GCP） | Cloud Native 化、RRF、再学習ループ、IaC/CI | Cloud Run, BigQuery, Dataform, Terraform, WIF |
| 5 | `5/study-hybrid-search-vertex/` | Vertex AI 差分移行 | Vertex Pipelines/Endpoints/Registry/Monitoring への adapter 差し替え | Vertex AI, KFP, Endpoint, Feature Group, Vizier |

---

## まずどこから始めるか

### 学習順（推奨）

1. `1/study-ml-foundations`  
2. `2/study-ml-app-pipeline`  
3. `3/study-hybrid-search-local`  
4. `4/study-hybrid-search-cloud`  
5. `5/study-hybrid-search-vertex`

### 目的別ショートカット

- **ML 基礎だけ学ぶ**: Phase 1
- **設計パターン（Port/Adapter）を学ぶ**: Phase 2, 3
- **GCP MLOps の運用全体**: Phase 4
- **Vertex AI への移行差分**: Phase 5

---

## 分割後の重要な変更点（Phase 1 -> 2）

- Phase 1 から `app/` と推論系を分離し、学習基礎フェーズに限定
- Phase 2 を新設し、API・DI・Port/Adapter・job 分離を導入
- Phase 1 と Phase 2 は独立運用（import 共有しない）
- モデル成果物の共有はしない前提（Phase 2 は Phase 2 内で学習して自己完結）

---

## 実行方式の段差（教材上の意図）

- **Phase 1, 2**: Docker Compose 中心  
  - ローカルで工程を分かりやすく追うことを優先
- **Phase 3**: `uv` ワークフロー + Docker Compose 併用  
  - 開発体験を modern Python 構成へ移行
- **Phase 4, 5**: クラウド実行基盤中心  
  - Cloud Run / BigQuery / Vertex AI で本番運用に近づける

この段差は「同じ思想を、基盤だけ置き換えていく」ための学習設計。

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

- `docs/Phase1-2分割タスク.md`  
  - Phase 1/2 分割の進捗・未完項目・判断履歴
- `docs/05_Docker配置規約.md`  
  - Dockerfile 配置と運用ルール
- 各 Phase 配下の `README.md` / `CLAUDE.md` / `docs/`  
  - その Phase の正本仕様

---

## 運用ルール（共通）

- 変更は原則 Phase 単位で閉じる
- 学習用途のため、重複コードは許容（意図的複製）
- Phase を跨ぐ共有ライブラリ化は優先しない
- ドキュメントは「現行フェーズの実態」を最優先で更新する

---

## 補足

構想段階では複数ドメイン案があったが、Phase 3 以降は不動産検索ドメインで統一。  
学習者が「モデル課題」ではなく「設計と移行差分」を追える構成を重視している。
