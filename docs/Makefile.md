# Makefile Command Index

更新日: 2026-04-24

この文書は各 Phase の Makefile コマンドを 1 か所で確認するための索引です。
実際の挙動と最新仕様のソースオブトゥルースは各 Phase の Makefile です。

対象:
- Phase 1: `1/study-ml-foundations/Makefile`
- Phase 2: `2/study-ml-app-pipeline/Makefile`
- Phase 3: `3/study-hybrid-search-local/Makefile`
- Phase 4: `4/study-hybrid-search-gcp/Makefile`
- Phase 5: `5/study-hybrid-search-vertex/Makefile`
- Phase 6: `6/study-hybrid-search-pmle/Makefile`
- Phase 7: `7/study-hybrid-search-gke/Makefile`

## 共通の見方

- Phase 1-3 はローカル実行中心です。
- Phase 4-7 は GCP / Vertex / GKE を含むクラウド実行中心です。
- まず一連の代表フローを回したい場合は `make run-all` を基準に見ると早いです。
- デプロイを伴う Phase では `make deploy-all` と `make run-all` は役割が分かれています。
	`deploy-all` は構築・配備、`run-all` は配備後の検証です。

## Phase 1

ソース: `1/study-ml-foundations/Makefile`

### 代表コマンド

| コマンド | 説明 |
|---|---|
| `make run-all` | monitor 付きで build → seed → train → test を実行 |
| `make run-all-core` | build → seed → train → test の本体フロー |
| `make test` | pytest 実行 |

### コマンド一覧

| コマンド | 説明 |
|---|---|
| `make help` | help を表示 |
| `make build` | Docker イメージを build |
| `make seed` | sklearn California Housing を PostgreSQL に投入 |
| `make train` | LightGBM 学習を実行 |
| `make test` | pytest 実行 |
| `make run-all-core` | build → seed → train → test |
| `make ops-run-all-monitor` | run-all 進捗を監視してログ保存 |
| `make run-all` | monitor 経由でエンドツーエンド実行 |
| `make down` | docker compose サービス停止・削除 |
| `make clean` | compose 停止と生成物削除 |
| `make free-ports` | host :5432 を使う他コンテナを解放 |

## Phase 2

ソース: `2/study-ml-app-pipeline/Makefile`

### 代表コマンド

| コマンド | 説明 |
|---|---|
| `make run-all` | monitor 付きで build → seed → train → test を実行 |
| `make run-all-core` | build → seed → train → test の本体フロー |
| `make test` | 非 E2E のローカル pytest |
| `make test-e2e` | Playwright E2E 実行 |

### コマンド一覧

| コマンド | 説明 |
|---|---|
| `make help` | help を表示 |
| `make build` | Docker イメージを build |
| `make seed` | sklearn California Housing を PostgreSQL に投入 |
| `make train` | LightGBM 学習を実行 |
| `make serve` | FastAPI を :8000 で起動 |
| `make test` | pytest 実行（E2E 除外） |
| `make test-e2e` | Playwright E2E 実行 |
| `make install-browsers` | Playwright 用 Chromium などをインストール |
| `make run-all-core` | build → seed → train → test |
| `make ops-run-all-monitor` | run-all 進捗を監視してログ保存 |
| `make run-all` | monitor 経由でエンドツーエンド実行 |
| `make down` | docker compose サービス停止・削除 |
| `make clean` | compose 停止と生成物削除 |
| `make free-ports` | host :5432 / :8000 を使う他コンテナを解放 |

## Phase 3

ソース: `3/study-hybrid-search-local/Makefile`

### 代表コマンド

| コマンド | 説明 |
|---|---|
| `make run-all` | monitor 付きでローカル検証フロー全体を実行 |
| `make run-all-core` | `ports-free` → `verify-pipeline` |
| `make verify-pipeline` | 起動・移行・検索・学習・精度確認まで代表 smoke を実行 |
| `make up-clean` | 競合ポート解放後に compose 起動 |

### ライフサイクル

| コマンド | 説明 |
|---|---|
| `make help` | help を表示 |
| `make up` | docker compose を detached で起動 |
| `make ports-free` | host :8000 / :5432 / :5050 / :7700 / :6379 を解放 |
| `make up-clean` | ポート解放後に起動 |
| `make wait-db` | postgres が ready になるまで待機 |
| `make build` | api イメージを build |
| `make down` | docker compose を停止 |
| `make logs` | api / postgres / meili / pgadmin / redis のログ追跡 |
| `make sync` | `uv sync --dev` |
| `make test` | pytest 実行（E2E 除外） |
| `make test-e2e` | Playwright E2E 実行 |
| `make install-browsers` | Playwright Chromium をインストール |
| `make check-layers` | AST ベースの layer check |
| `make api-refresh` | api サービスだけ再 build・再 recreate |

### DB / セットアップ

| コマンド | 説明 |
|---|---|
| `make db-migrate-core` | migration 001: properties 作成 |
| `make db-seed-properties` | migration 002: properties seed |
| `make db-migrate-ops` | migration 003: logs / stats 作成 |
| `make db-migrate-features` | migration 004: features / batch logs |
| `make db-migrate-embeddings` | migration 005: ME5 embeddings |
| `make db-migrate-learning` | migration 006+007: learning logs / ranking compare logs |
| `make db-migrate-eval` | migration 008: eval / kpi tables |
| `make ops-bootstrap` | 初回セットアップ一式 |

### 検索 / 運用 / 学習

| コマンド | 説明 |
|---|---|
| `make ops-sync` | PostgreSQL → Meilisearch 同期 |
| `make ops-livez` | health check |
| `make ops-search` | `/search` smoke |
| `make ops-search-components` | Meili / ME5 / LightGBM 寄与を厳密確認 |
| `make ops-feedback` | `/search` → `/feedback` round-trip |
| `make ops-ranking` | rerank 出力確認 |
| `make ops-ranking-verbose` | lgbm / me5 スコア詳細確認 |
| `make ops-label-seed` | feedback イベント seed |
| `make ops-accuracy-report` | nDCG / HitRate / MRR の簡易レポート |
| `make features-daily` | 日次特徴量集計 |
| `make features-report` | feature レポート出力 |
| `make ops-embed` | ME5 property embeddings 生成 |
| `make ops-train-build` | 学習データセット構築 |
| `make ops-train-fit` | LambdaRank 学習 |
| `make ops-train-fit-safe` | empty data に強い安全版学習 |
| `make eval-compare` | Meili vs rerank 比較レポート |
| `make eval-offline` | Offline NDCG / MAP / Recall 評価 |
| `make kpi-daily` | 日次 KPI 集計 |
| `make eval-weekly-report` | 週次評価レポート出力 |
| `make ops-retrain` | 週次 retraining orchestration |
| `make ops-daily` | 日次の sync / feature / embed / KPI |
| `make ops-weekly` | 週次の evaluate / report / retrain |

### 集約フロー

| コマンド | 説明 |
|---|---|
| `make verify-pipeline` | 代表的な end-to-end smoke |
| `make run-all-core` | `ports-free` 後に `verify-pipeline` |
| `make ops-run-all-monitor` | run-all 進捗を監視してログ保存 |
| `make run-all` | monitor 経由で end-to-end 実行 |

## Phase 4

ソース: `4/study-hybrid-search-gcp/Makefile`

### 代表コマンド

| コマンド | 説明 |
|---|---|
| `make deploy-all` | Terraform + Cloud Run 配備 |
| `make run-all` | 配備後の総合検証 |
| `make check` | lint + fmt-check + typecheck + test |

### 開発 / 品質

| コマンド | 説明 |
|---|---|
| `make help` | help を表示 |
| `make doctor` | 必須ツール確認 |
| `make sync` | `uv sync --all-packages --dev` |
| `make test` | pytest 実行 |
| `make lint` | ruff check |
| `make fmt` | ruff format |
| `make fmt-check` | ruff format --check |
| `make typecheck` | mypy strict |
| `make check` | lint / fmt-check / typecheck / test |
| `make sync-dataform-config` | dataform 設定再生成 |
| `make check-layers` | AST ベース layer check |

### Terraform / 配備

| コマンド | 説明 |
|---|---|
| `make tf-bootstrap` | API 有効化 + tfstate bucket 作成 |
| `make tf-init` | terraform init |
| `make tf-validate` | terraform validate |
| `make tf-fmt` | terraform fmt --check |
| `make tf-fmt-fix` | terraform fmt |
| `make tf-plan` | terraform plan |
| `make deploy-all` | provisioning + rollout（monitor 付き安全経路） |
| `make deploy-all-direct` | monitor なしの deploy-all |
| `make ops-deploy-monitor` | deploy-all のリアルタイム監視 |
| `make ops-deploy-checker` | build success + readyz + component gate の事後確認 |
| `make destroy-all` | Terraform 管理リソース全削除 |

### ローカル smoke / deploy

| コマンド | 説明 |
|---|---|
| `make seed-test` | 5 件の test properties を投入 |
| `make seed-test-clean` | test seed データ削除 |
| `make train-smoke` | ローカル dry-run 学習 |
| `make train-smoke-persist` | dry-run 学習モデルを保存 |
| `make api-dev` | debug 用ローカル API 起動 |
| `make api-dev-search-rerank` | ローカル `/search` + rerank 有効起動 |
| `make docker-auth` | Artifact Registry 用 docker 認証 |
| `make deploy-api-local` | Cloud Build + Cloud Run deploy |
| `make deploy-training-job-local` | Cloud Build + Cloud Run jobs update |
| `make run-training-job-local` | training-job を 1 回実行 |
| `make clean` | `.venv` / `.terraform` / cache 削除 |

### 運用 / 検証

| コマンド | 説明 |
|---|---|
| `make ops-api-url` | search-api URL を表示 |
| `make ops-daily` | 3 つの日次確認をまとめて実行 |
| `make ops-skew-latest` | 当日の skew 結果確認 |
| `make ops-search-volume` | 24h の `/search` リクエスト量 |
| `make ops-runs-recent` | 直近 5 件の学習 run |
| `make ops-skew-run` | skew SQL を ad-hoc 実行 |
| `make ops-bq-scan-top` | BQ scan 上位 20 件 |
| `make ops-train-now` | training-job を即時実行 |
| `make ops-reload-api` | API に最新 model 再読込を促す |
| `make ops-enable-search` | Cloud Run で検索機能を有効化 |
| `make ops-livez` | `/livez` 確認 |
| `make ops-search` | `/search` smoke |
| `make ops-search-components` | lexical / ME5 / LightGBM 寄与確認 |
| `make local-search-components` | ローカル API 向け component gate |
| `make ops-accuracy-report` | GCP API 向け ranking accuracy report |
| `make local-accuracy-report` | ローカル API 向け ranking accuracy report |
| `make ops-ranking` | ranking 出力確認 |
| `make ops-feedback` | feedback round-trip |
| `make ops-label-seed` | feedback seed |
| `make ops-check-retrain` | retrain 判定 API 呼び出し |
| `make run-all` | 配備後の総合 validation flow |

## Phase 5

ソース: `5/study-hybrid-search-vertex/Makefile`

### 代表コマンド

| コマンド | 説明 |
|---|---|
| `make deploy-all` | Terraform + Vertex / Cloud Run 配備 |
| `make run-all` | 配備後の総合検証 |
| `make ops-train-now` | Vertex AI へ train pipeline を submit |

### 開発 / 品質

| コマンド | 説明 |
|---|---|
| `make help` | help を表示 |
| `make doctor` | 必須ツール確認 |
| `make sync` | `uv sync --dev` |
| `make test` | pytest 実行 |
| `make lint` | ruff check |
| `make fmt` | ruff format |
| `make fmt-check` | ruff format --check |
| `make typecheck` | mypy strict |
| `make check` | lint / fmt-check / typecheck / test |
| `make sync-dataform-config` | dataform 設定再生成 |
| `make check-layers` | AST ベース layer check |

### Terraform / セットアップ / 配備

| コマンド | 説明 |
|---|---|
| `make tf-bootstrap` | API 有効化 + tfstate bucket 作成 |
| `make tf-init` | terraform init |
| `make tf-validate` | terraform validate |
| `make tf-fmt` | terraform fmt --check |
| `make tf-fmt-fix` | terraform fmt |
| `make tf-plan` | terraform plan |
| `make setup-model-monitoring` | Vertex Model Monitoring 設定 payload 表示 |
| `make setup-pipeline-schedule` | Vertex Pipeline schedule 設定 payload 表示 |
| `make deploy-all` | provisioning + search-api rollout |
| `make deploy-all-direct` | Phase4 互換 alias |
| `make ops-deploy-monitor` | deploy-all のリアルタイム監視 |
| `make destroy-all` | Terraform 管理リソース全削除 |

### ローカル smoke / deploy

| コマンド | 説明 |
|---|---|
| `make seed-test` | 5 件の test properties を投入 |
| `make seed-test-clean` | test seed データ削除 |
| `make train-smoke` | ローカル dry-run 学習 |
| `make train-smoke-persist` | dry-run 学習モデル保存 |
| `make api-dev` | ローカル uvicorn 起動 |
| `make docker-auth` | Artifact Registry 用 docker 認証 |
| `make deploy-api-local` | Cloud Build + Cloud Run deploy |
| `make deploy-training-job-local` | 廃止済み。`make ops-train-now` へ誘導 |
| `make clean` | `.venv` / `.terraform` / cache 削除 |

### 運用 / 検証

| コマンド | 説明 |
|---|---|
| `make ops-api-url` | search-api URL 表示 |
| `make ops-daily` | 3 つの日次確認 |
| `make ops-skew-latest` | skew 結果確認 |
| `make ops-search-volume` | `/search` volume 確認 |
| `make ops-runs-recent` | 直近学習 run 確認 |
| `make ops-skew-run` | skew SQL を ad-hoc 実行 |
| `make ops-bq-scan-top` | BQ scan 上位確認 |
| `make ops-train-now` | Vertex AI へ train pipeline submit |
| `make ops-pipeline-run` | embed / train pipeline を手動 submit |
| `make ops-promote-reranker` | reranker promotion plan 出力 / 適用 |
| `make ops-reload-api` | API に model 再読込を促す |
| `make ops-enable-search` | Vertex endpoint mode へ切替 |
| `make ops-livez` | `/livez` 確認 |
| `make ops-search` | `/search` smoke |
| `make ops-search-components` | lexical / semantic / rerank 寄与確認 |
| `make ops-ranking` | ranking 出力確認 |
| `make ops-feedback` | feedback round-trip |
| `make ops-label-seed` | feedback seed |
| `make ops-check-retrain` | retrain 判定 API 呼び出し |
| `make ops-accuracy-report` | GCP API 向け ranking accuracy report |
| `make local-accuracy-report` | ローカル API 向け accuracy report |
| `make run-all` | 配備後の総合 validation flow |

## Phase 6

ソース: `6/study-hybrid-search-pmle/Makefile`

### 代表コマンド

| コマンド | 説明 |
|---|---|
| `make deploy-all` | Terraform + Vertex / Cloud Run 配備 |
| `make run-all` | 配備後の総合検証 |
| `make setup-encoder-endpoint` | encoder endpoint 登録 / deploy |
| `make setup-reranker-endpoint` | reranker endpoint 登録 / deploy |

### Phase 5 から継続して使う主コマンド

Phase 6 の基本コマンド群は Phase 5 とほぼ同じです。`doctor` / `sync` / `test` / `lint` / `fmt` / `fmt-check` / `typecheck` / `check` / `tf-*` / `deploy-all` / `destroy-all` / `seed-test` / `train-smoke` / `ops-*` / `run-all` は継続です。

### Phase 6 で追加・拡張された主なコマンド

| コマンド | 説明 |
|---|---|
| `make setup-encoder-endpoint` | property-encoder を登録 / deploy（既定 dry-run、`APPLY=1` で実行） |
| `make setup-reranker-endpoint` | property-reranker を登録 / deploy（既定 dry-run、`APPLY=1` で実行） |
| `make ops-monitor` | 任意コマンドを monitor 付きで実行 |
| `make ops-monitor-lro` | 長時間無出力の LRO 向け monitor |
| `make destroy-phase6-learning` | endpoint + GCS artifacts の軽量 coast-down |
| `make ops-slo-status` | availability / latency SLO の burn-rate 確認 |
| `make bqml-train-popularity` | BQML property-popularity モデル学習 |
| `make enrich-properties` | Gemini による物件説明 enrichment |

## Phase 7

ソース: `7/study-hybrid-search-gke/Makefile`

### 代表コマンド

| コマンド | 説明 |
|---|---|
| `make deploy-all` | Terraform + GKE + KServe + API 配備 |
| `make run-all` | 配備後の総合検証 |
| `make deploy-api` | GKE の search-api イメージ更新 |
| `make deploy-kserve-models` | KServe InferenceService に model 反映 |

### Phase 6 から継続して使う主コマンド

Phase 7 も開発・品質・Terraform・運用の大半は Phase 6 と同系です。`doctor` / `sync` / `test` / `lint` / `fmt` / `fmt-check` / `typecheck` / `check` / `tf-*` / `deploy-all` / `ops-deploy-monitor` / `destroy-all` / `seed-test` / `train-smoke` / `ops-*` / `run-all` は継続です。

### Phase 7 で追加・変更された主なコマンド

| コマンド | 説明 |
|---|---|
| `make deploy-api` | Cloud Build + `kubectl set image` で search-api 更新 |
| `make deploy-kserve-models` | Model Registry artifacts を KServe InferenceService へ同期 |
| `make kube-creds` | GKE Autopilot cluster の kubeconfig 取得 |
| `make ops-api-url` | Cloud Run ではなく Gateway external URL を表示 |
| `make ops-reload-api` | Cloud Run update ではなく `kubectl rollout restart` を実行 |

## 使い分けの目安

| 目的 | まず見るコマンド |
|---|---|
| Phase を一通り実行したい | `make run-all` |
| 配備したい | `make deploy-all` |
| 監視付きで長時間処理を見たい | Phase 1-3 は `make ops-run-all-monitor`、Phase 4-7 は `make ops-deploy-monitor` |
| 日次確認だけしたい | `make ops-daily` |
| 検索 API の疎通を見たい | `make ops-livez` / `make ops-search` |
| 厳密な検索寄与を見たい | `make ops-search-components` |
| 学習を即時実行したい | `make ops-train-now` |

## 補足

- この文書は概要索引です。引数や環境変数の override は各 Makefile のコメントを優先してください。
- `Phase 6` と `Phase 7` は `Phase 5` 系統を拡張した構成のため、共通コマンドが多いです。差分コマンドだけ上で強調しています。
