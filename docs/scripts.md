# scripts 一覧 (Phase 1-7)

このドキュメントは、各 Phase の scripts 配下にある実行スクリプトを
"どの役割で使うか" と "どの名前で存在するか" の観点で整理したものです。

対象パス:
- 1/study-ml-foundations/scripts
- 2/study-ml-app-pipeline/scripts
- 3/study-hybrid-search-local/scripts
- 4/study-hybrid-search-gcp/scripts
- 5/study-hybrid-search-vertex/scripts
- 6/study-hybrid-search-pmle/scripts
- 7/study-hybrid-search-gke/scripts

除外:
- __pycache__
- .gitkeep

---

## Phase 1: study-ml-foundations

### 共通/基盤
- core.py: コンテナ競合解消や共通処理のユーティリティ

### Setup/Train
- local/setup/seed.py: 学習用データ seed
- local/setup/train.py: 学習実行

### Ops/Test
- local/ops/test.py: pytest 実行
- local/ops/clean.py: 生成物クリーンアップ
- local/run_all_monitor.py: run-all 監視ラッパー

### ドキュメント
- README.md: scripts の使い方

## Phase 2: study-ml-app-pipeline

### 共通/基盤
- core.py: コンテナ/ポート競合解消などの共通ユーティリティ

### Setup/Train/Deploy
- local/setup/seed.py: seed データ投入
- local/setup/train.py: 学習実行
- local/deploy/serve.py: ローカル API 起動

### Ops/Test
- local/ops/test.py: pytest 実行
- local/ops/clean.py: クリーンアップ
- local/run_all_monitor.py: run-all 監視ラッパー

## Phase 3: study-hybrid-search-local

### CI
- ci/layers.py: レイヤ依存ルール検査

### Setup/Runtime
- local/setup/compose.sh: docker compose ラッパー
- local/setup/free_ports.sh: 使用ポート解放

### Ops (検索/学習/評価)
- local/ops/health_check.py: API ヘルスチェック
- local/ops/search_check.py: 検索 smoke
- local/ops/search_component_check.py: 検索コンポーネント寄与チェック
- local/ops/ranking_check.py: ランキング挙動確認
- local/ops/ranking_check_verbose.py: 詳細ランキング確認
- local/ops/feedback_check.py: feedback 経路確認
- local/ops/training_label_seed.py: ラベル seed
- local/ops/training_fit_safe.py: 学習安全実行
- local/ops/accuracy_report.py: 精度レポート
- local/run_all_monitor.py: run-all 監視ラッパー

### ドキュメント
- README.md
- ci/README.md
- dev/README.md
- local/README.md

## Phase 4: study-hybrid-search-gcp

### 共通/基盤
- _common.py: 設定/共通処理

### CI
- ci/check_layers.py: レイヤ依存検査

### Dev (Terraform/環境/seed)
- dev/doctor.py: 環境検査
- dev/config_init.py: 初期設定生成
- dev/sync_dataform.py: Dataform 設定同期
- dev/tf_bootstrap.py: Terraform 事前準備
- dev/tf_init.py: Terraform init
- dev/tf_plan.py: Terraform plan
- dev/deploy_all.py: デプロイ集約
- dev/destroy_all.py: リソース削除
- dev/seed_minimal.py: 最小 seed
- dev/seed_minimal_clean.py: 最小 seed 削除

### Local Ops/Deploy
- local/deploy_monitor.py: deploy/run 監視
- local/deploy_checker.py: デプロイ後検証
- local/deploy_init.py: デプロイ初期化
- local/deploy_api.py: API デプロイ
- local/deploy_training_job.py: training job デプロイ
- local/run_training_job.py: training job 実行
- local/livez_check.py: livez
- local/search_check.py: search
- local/search_component_check.py: search component
- local/ranking_check.py: ranking
- local/feedback_check.py: feedback
- local/training_label_seed.py: ラベル seed
- local/check_retrain.py: 再学習判定
- local/accuracy_report.py: 精度レポート

### SQL (運用クエリ)
- local/sql/skew_latest.sql
- local/sql/search_volume.sql
- local/sql/runs_recent.sql
- local/sql/bq_scan_top.sql

## Phase 5: study-hybrid-search-vertex

### 共通/CI
- _common.py: 共通設定ユーティリティ
- ci/layers.py: レイヤ検査
- ci/sync_dataform.py: Dataform 同期

### Setup (Terraform/Vertex)
- local/setup/doctor.py
- local/setup/tf_bootstrap.py
- local/setup/tf_init.py
- local/setup/tf_plan.py
- local/setup/create_schedule.py
- local/setup/setup_model_monitoring.py
- local/setup/setup_encoder_endpoint.py
- local/setup/upload_encoder_assets.py
- local/setup/deploy_all.py
- local/setup/destroy_all.py
- local/setup/seed_minimal.py
- local/setup/seed_minimal_clean.py
- local/setup/print_github_variables.py

### Deploy/Ops
- local/deploy_monitor.py: deploy/run 監視
- local/deploy/api_local.py: API デプロイ
- local/deploy/training_job_local.py: training job デプロイ
- local/ops/livez_check.py
- local/ops/search_check.py
- local/ops/search_component_check.py
- local/ops/ranking_check.py
- local/ops/feedback_check.py
- local/ops/training_label_seed.py
- local/ops/check_retrain.py
- local/ops/accuracy_report.py
- local/ops/sync_meili.py: Meilisearch 同期
- local/ops/register_model.py: モデル登録
- local/ops/promote.py: モデル昇格

### SQL
- local/sql/skew_latest.sql
- local/sql/search_volume.sql
- local/sql/runs_recent.sql
- local/sql/bq_scan_top.sql

## Phase 6: study-hybrid-search-pmle

### 共通/CI/BQML
- _common.py
- ci/layers.py
- ci/sync_dataform.py
- bqml/train_popularity.sql: BQML 学習 SQL
- local/bqml/train_popularity.py: BQML 学習実行

### Setup (PMLE/Endpoint)
- local/setup/doctor.py
- local/setup/tf_bootstrap.py
- local/setup/tf_init.py
- local/setup/tf_plan.py
- local/setup/create_schedule.py
- local/setup/setup_model_monitoring.py
- local/setup/setup_encoder_endpoint.py
- local/setup/setup_reranker_endpoint.py
- local/setup/upload_encoder_assets.py
- local/setup/deploy_all.py
- local/setup/destroy_all.py
- local/setup/destroy_phase6_learning.py
- local/setup/seed_minimal.py
- local/setup/seed_minimal_clean.py
- local/setup/print_github_variables.py

### Deploy/Ops/Enrichment
- local/deploy_monitor.py
- local/deploy/api_local.py
- local/deploy/training_job_local.py
- local/enrichment/run_enrichment.py
- local/ops/livez_check.py
- local/ops/search_check.py
- local/ops/search_component_check.py
- local/ops/ranking_check.py
- local/ops/feedback_check.py
- local/ops/training_label_seed.py
- local/ops/check_retrain.py
- local/ops/accuracy_report.py
- local/ops/sync_meili.py
- local/ops/register_model.py
- local/ops/promote.py
- local/ops/slo_status.py

### SQL
- local/sql/skew_latest.sql
- local/sql/search_volume.sql
- local/sql/runs_recent.sql
- local/sql/bq_scan_top.sql

## Phase 7: study-hybrid-search-gke

### 共通/CI/BQML
- _common.py
- ci/layers.py
- ci/sync_dataform.py
- bqml/train_popularity.sql
- local/bqml/train_popularity.py

### Setup (GKE)
- local/setup/doctor.py
- local/setup/tf_bootstrap.py
- local/setup/tf_init.py
- local/setup/tf_plan.py
- local/setup/create_schedule.py
- local/setup/setup_model_monitoring.py
- local/setup/deploy_all.py
- local/setup/destroy_all.py
- local/setup/seed_minimal.py
- local/setup/seed_minimal_clean.py
- local/setup/print_github_variables.py

### Deploy/Ops/Enrichment
- local/deploy_monitor.py
- local/deploy/api_gke.py: GKE API デプロイ
- local/deploy/kserve_models.py: KServe モデル反映
- local/deploy/training_job_local.py
- local/enrichment/run_enrichment.py
- local/ops/livez_check.py
- local/ops/search_check.py
- local/ops/search_component_check.py
- local/ops/ranking_check.py
- local/ops/feedback_check.py
- local/ops/training_label_seed.py
- local/ops/check_retrain.py
- local/ops/accuracy_report.py
- local/ops/sync_meili.py
- local/ops/register_model.py
- local/ops/promote.py
- local/ops/slo_status.py

### SQL
- local/sql/skew_latest.sql
- local/sql/search_volume.sql
- local/sql/runs_recent.sql
- local/sql/bq_scan_top.sql