
# study-gcp-mlops

---

## 1. 目的

```text
MLOpsをCloud Runベースで理解・実装する

・Kubernetesを使わない構成でMLパイプラインを構築する
・バッチ処理主体のMLフロー（学習・評価・モデル保存）を確立する
・BigQueryで評価メトリクスを蓄積し、最良モデルを機械的に選択する
・推論APIで最良モデルを自動ロードし、MLOpsの一周を完成させる
・監視・ドリフト検知で運用品質を担保する
```

---

## 2. 技術スタック

```text
GCP
- Cloud Run（Job / Service）
- GCS（logs / models）
- BigQuery（評価メトリクス蓄積・最良モデル選択・90日リテンション）
- Artifact Registry
- Cloud Scheduler（定期実行）

ML
- scikit-learn（California Housing / RandomForest）
- MLflow（実験管理・メトリクス記録）
- pandas

API
- FastAPI（Cloud Run Service / 推論API）

IaC
- Terraform

CI/CD
- GitHub Actions（batch / API / Terraform 3本）

監視・運用
- Discord通知（batch監視・API健全性・モデルドリフト検知）
- JSON構造化ログ（Cloud Logging互換）
- エラーリトライ（exponential backoff）

将来
- Vertex AI
```

---

## 3. アーキテクチャ

```text
[Cloud Run Job（batch）]
   ├── California Housing データ取得
   ├── train/test 分割
   ├── scikit-learn RandomForest 学習
   ├── 評価（RMSE, MAE）→ MLflow記録
   ├── モデル保存 → [GCS models/]
   ├── ログ出力 → [GCS logs/]
   └── メトリクス投入 → [BigQuery mlops.metrics]

[BigQuery]
   └── metrics テーブル → 最良モデル選択（ORDER BY rmse ASC LIMIT 1）

[Cloud Run Service（API）]
   ├── 起動時に BigQuery から最良モデルパス取得
   ├── GCS からモデルロード
   └── FastAPI で推論レスポンス（POST /predict）

[Cloud Scheduler]
   └── 毎日 9:00 JST に batch を定期実行

[GitHub Actions]
   ├── batch: main push(src/batch) → test → build → push → Cloud Run Job 更新
   ├── api:   main push(src/api)   → test → build → push → Cloud Run Service 更新
   └── tf:    main push(terraform)  → plan → apply

[監視]
   ├── batch-monitor  → Cloud Run Job実行結果 → Discord通知
   ├── api-monitor    → /health チェック → Discord異常通知
   └── drift-check    → RMSE閾値チェック → Discord WARNING通知
```

---

## 4. ディレクトリ構成

```text
study-gcp-mlops/
├── .github/workflows/  # CI/CD（batch / API / Terraform）
├── src/
│   ├── batch/          # Cloud Run Job（ML学習パイプライン）
│   └── api/            # Cloud Run Service（FastAPI推論API）
├── terraform/          # インフラ定義（Terraform）
├── makefiles/          # Makefile分割ファイル
├── scripts/            # 共通ユーティリティ・監視・デプロイスクリプト
├── docs/               # 手順書・ドキュメント
├── Makefile            # ビルド・デプロイコマンド
└── README.md
```

---

## 5. 使い方

### 初回セットアップ

```bash
./scripts/setup_gcp.sh        # GCP CLIインストール
./scripts/setup_terraform.sh   # Terraformインストール
gcloud init                    # GCPログイン & プロジェクト設定
make gcp-setup                 # API有効化・SA権限・Docker認証
```

### デプロイ & 実行

```bash
make deploy          # 全体デプロイ（batch + API）
make batch-run       # Cloud Run Job実行
make batch-logs      # 実行履歴確認
make api-url         # APIのURL表示
```

### ローカル開発

```bash
make test             # 全テスト一括実行（22件）
make batch-test       # batchテスト実行（16件）
make batch-run-local  # ローカルでML学習実行
make batch-ui         # MLflow UI起動
make api-test         # APIテスト実行（6件）
```

### 監視

```bash
make batch-monitor    # batch実行結果チェック + Discord通知
make api-monitor      # API健全性チェック + Discord通知
make batch-drift      # モデルドリフト検知
```

### リセット

```bash
make reset           # 全リソース削除 & クリーン
```

### コマンド一覧

```bash
make help
```
