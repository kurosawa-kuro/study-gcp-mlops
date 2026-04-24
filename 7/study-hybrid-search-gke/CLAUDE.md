# CLAUDE.md

本リポジトリ (`7/study-hybrid-search-gke`) で作業する Claude Code 向けのガイド。**Phase 7 は Phase 6 (`6/study-gcp-ml-engineer-cert/`) の PMLE 技術統合をそのまま継承した上で、Serving 層のみを Vertex AI Endpoint から GKE + KServe InferenceService に差し替えた Draft フェーズ**。中核コード (不動産ハイブリッド検索) は変えず、encoder / reranker の推論呼び出しを cluster-local HTTP に切り替える。

ドキュメント全般の運用規約は [`docs/README.md`](docs/README.md)、スコープの決定権は [`docs/02_移行ロードマップ.md`](docs/02_移行ロードマップ.md)。本 CLAUDE.md はそれらに従属する。

---

## 最初に読むもの (順番)

1. [`docs/02_移行ロードマップ.md §0`](docs/02_移行ロードマップ.md) — Phase 6 からの差分 (Serving 層のみ GKE + KServe に差し替え)
2. [`docs/01_仕様と設計.md §3`](docs/01_仕様と設計.md) — 各 PMLE 統合トピックのファイル配置 (Phase 6 から継承)
3. [`docs/03_実装カタログ.md`](docs/03_実装カタログ.md) + [`docs/04_運用.md`](docs/04_運用.md) — 実装 / 運用詳細
4. `infra/manifests/` — GKE Deployment / KServe InferenceService / NetworkPolicy マニフェスト

---

## hybrid-search-gke の設計テーゼ (題材: 不動産ハイブリッド検索)

- **題材**: 自由文クエリ + フィルタ → 物件ランキング上位 20 件。3 段構成 = (1a) Meilisearch BM25、(1b) BigQuery VECTOR_SEARCH、(2) RRF 融合、(3) LightGBM `lambdarank` 再ランク
- **Phase 6 PMLE 技術 (RAG / BQML / Agent Builder / Vertex Vector Search / SLO / Dataflow) を完全継承**。Serving 層のみ GKE + KServe に差し替え
- **学習 = Vertex AI Pipelines (`embed_pipeline` + `train_pipeline`) / 推論 = GKE Deployment (`search-api`) + KServe InferenceService (`property-encoder` / `property-reranker`)**。モデルは API コンテナへ同梱せず、`search-api` は `KServeEncoder` / `KServeReranker` を通して cluster-local HTTP で推論を委譲する

---

## 非負制約 (User 確認無しに変えない)

### 不変 — 絶対に変えない

| 項目 | 値 |
|---|---|
| **題材 / ドメイン** | 不動産ハイブリッド検索 (クエリ + フィルタ → 物件ランキング上位 20 件) |
| **ハイブリッド検索中核** | Meilisearch BM25 (lexical) + BQ `VECTOR_SEARCH` + multilingual-e5 (semantic) + RRF 融合 + LightGBM LambdaRank (rerank) の挙動 / データフロー / デフォルト `/search` レスポンス |
| **親リポ非負制約** | GCP プロジェクト `mlops-dev-a` / リージョン `asia-northeast1` / Python 3.12 / uv workspace / Terraform 1.9+ / WIF (SA Key 禁止) / 10 SA 最小権限分離 |
| **default feature flag 値** | Phase 6 から継承した flag (`SEMANTIC_BACKEND` / `LEXICAL_BACKEND` / `BQML_POPULARITY_ENABLED` 等) は default で Phase 5/6 挙動を維持 (`bq` / `meili` / `false`) |

| 項目 | 値 | 理由 |
|---|---|---|
| GCP プロジェクト | `mlops-dev-a` | 固定 |
| リージョン | `asia-northeast1` | 固定 |
| Python | 3.12 | `pyproject.toml` |
| パッケージ管理 | `uv` (pip / poetry 不可) | workspace 採用 |
| IaC | Terraform 1.9+ | |
| GKE Autopilot | `asia-northeast1` リージョナル、Gateway API + Workload Identity 既定有効 | Phase 7 serving 層の実行基盤 |
| search-api Deployment | `requests=500m/1Gi`, `limits=2/2Gi`, `minReplicas=1 maxReplicas=10` (HPA CPU 70% / Mem 80%) | |
| KServe 認可境界 | NetworkPolicy で search namespace → kserve-inference namespace の in-cluster アクセスのみ許可 | |
| Service Account | Phase 6 の 10 SA 分離を継承。GKE KSA (search/search-api, kserve-inference/encoder, kserve-inference/reranker) に Workload Identity で bind | |

---

## Feature parity invariant (6 ファイル同 PR 原則)

Phase 6 から継承。特徴量を追加 / 変更するとき、以下 6 つを **必ず同じ PR で揃える**:

1. `definitions/features/property_features_daily.sqlx`
2. `ml/common/feature_engineering.py::build_ranker_features`
3. `ml/common/schema/feature_schema.py::FEATURE_COLS_RANKER`
4. `infra/terraform/modules/data/main.tf` の `ranking_log.features` RECORD
5. `monitoring/validate_feature_skew.sql` の UNPIVOT
6. `infra/terraform/modules/vertex/main.tf::google_vertex_ai_feature_group_feature` × N

---

## ドキュメント衝突時の権威順位

`docs/README.md §2` に従う:

```
02_移行ロードマップ.md > 01_仕様と設計.md > README.md
```

`CLAUDE.md` と `03_実装カタログ.md` は上位 3 者から派生する従属ドキュメント。

---

## 開発コマンド

生コマンドは `docs/04_運用.md §1` の STEP、全ターゲットは `make help`。`make check` でローカル CI 同等 (ruff / ruff format / mypy strict / pytest) を走らせる。

| target | 用途 |
|---|---|
| `make doctor` | 前提ツール到達確認 |
| `make sync` | uv workspace + dev group 同期 |
| `make check` | ruff + fmt-check + mypy + pytest (CI 同等) |
| `make check-layers` | AST で Port/Adapter 境界違反を検出 |
| `make train-smoke` | 合成データで LightGBM LambdaRank 学習 (GCP 認証不要) |
| `make api-dev` | ローカル uvicorn (`ENABLE_SEARCH=false` 既定) |
| `make tf-validate` | オフライン terraform validate |
| `make tf-bootstrap` | Phase 0 (API 有効化 + tfstate バケット作成、冪等) |
| `make tf-plan` | Terraform plan |
| `make kube-creds` | 対象 GKE Autopilot クラスタの kubeconfig を取得 |
| `make deploy-api` | Cloud Build → Artifact Registry → `kubectl set image` で rollout |
| `make deploy-kserve-models` | Vertex Model Registry の `production` alias artifact URI を引いて KServe InferenceService を更新 |
| `make ops-reload-api` | `kubectl rollout restart deployment/search-api` で rolling restart |
| `make ops-slo-status` | Phase 6 T5: SLO compliance + burn-rate を表示 |
| `make bqml-train-popularity` | Phase 6 T1: BQML property-popularity model 学習 |
| `make enrich-properties` | Phase 6 T8: Gemini description enrichment |
| `make ops-*` | 本番 GCP 操作 (livez / search / ranking / feedback / label-seed 等) |

---

## GKE 固有の注意点

- **KServe URL**: `KSERVE_ENCODER_URL` / `KSERVE_RERANKER_URL` は cluster-local DNS (`http://<svc>.<ns>.svc.cluster.local/...`)。`infra/manifests/search-api/deployment.yaml` で ConfigMap に注入
- **KServe InferenceService の storageUri 更新**: `scripts/local/deploy/kserve_models.py` が Vertex Model Registry の `production` alias を引いて `kubectl patch` で書き換える。`make deploy-kserve-models` でラッパー
- **2 段階 apply**: 初回 Terraform apply は `-target=module.gke -target=module.iam -target=module.data` で cluster / IAM / storage を先行作成。provider.tf の kubernetes/helm provider が cluster 完成後に有効化されるため
- **Kubernetes Secret `meili-master-key`**: ExternalSecrets Operator 未導入のため Secret Manager から手動同期が必要。`env/secret/README.md` に手順あり
- **Vertex AI Endpoint は使わない**: encoder / reranker の推論は KServe 経由。`kserve_encoder_url` / `kserve_reranker_url` に cluster-local URL を設定する
- **Phase 6 PMLE 技術はそのまま**: RAG (`/rag`), BQML popularity, Agent Builder 副経路, Vertex Vector Search, SLO, Dataflow streaming は Phase 6 と同一実装。Vertex Endpoint 部分だけ KServe に差し替え済み

---

## Port / Adapter 境界と make check

Phase 6 から継承。新しいコードを追加するときの基準:

- **Port**: `app/services/protocols/<name>.py` の Protocol
- **Adapter**: `app/services/adapters/<name>.py`。外部 SDK 依存はここでのみ
- **Service**: `app/services/<name>.py`。Port だけ import、adapter import 禁止
- **境界検知**: `scripts/ci/layers.py::RULES` に新 Port / service を追加

---

## 書き方

`docs/README.md §4` 書き方ルールに従う:
- 日本語で書く。英単語は技術用語としてそのまま
- コマンドは `make` ターゲット優先
- 識別子は固有名を使う (`<foo>` でぼかさない)
- STEP / 番号付きリストは上から叩けば成立する順序で書く
- 推測で書かない
