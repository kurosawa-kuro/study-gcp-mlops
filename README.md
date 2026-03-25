
# study-gcp-mlops

---

## 1. 目的

```text
MLOpsをCloud Runベースで理解・実装する

・Kubernetesを使わない構成でMLパイプラインを構築する
・バッチ処理主体のMLフロー（学習・評価・モデル保存）を確立する
・推論APIまで含めた一連の流れを実装する
```

---

## 2. 技術スタック

```text
GCP
- Cloud Run（Job / Service）
- GCS（logs / models）
- Artifact Registry
- Cloud Scheduler（定期実行）

ML
- scikit-learn（California Housing / RandomForest）
- MLflow（実験管理・メトリクス記録）
- pandas

API（将来）
- FastAPI

IaC
- Terraform

CI/CD
- GitHub Actions

将来
- BigQuery（features / predictions / metrics）
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
   └── ログ出力 → [GCS logs/]

[Cloud Scheduler]
   └── 毎日 9:00 JST に batch を定期実行

[GitHub Actions]
   └── main push → test → build → push → Cloud Run Job 更新

---（将来）---

[Cloud Run Service（API）]
   └── GCS からモデルロード → FastAPI 推論レスポンス
```

---

## 4. ディレクトリ構成

```text
study-gcp-mlops/
├── .github/workflows/  # CI/CD（GitHub Actions）
├── src/
│   ├── batch/          # Cloud Run Job（ML学習パイプライン）
│   └── api/            # Cloud Run Service（FastAPI）（将来）
├── terraform/          # インフラ定義（Terraform）
├── makefiles/          # Makefile分割ファイル
├── scripts/            # セットアップ・デプロイスクリプト
├── docs/               # 手順書・ドキュメント
├── Makefile            # ビルド・デプロイコマンド
└── README.md
```

---

## 5. 使い方

### 初回セットアップ

```bash
./scripts/setup-gcp.sh        # GCP CLIインストール
./scripts/setup-terraform.sh   # Terraformインストール
gcloud init                    # GCPログイン & プロジェクト設定
make gcp-setup                 # API有効化・SA権限・Docker認証
```

### デプロイ & 実行

```bash
make deploy          # 全体デプロイ（インフラ + batch）
make batch-run       # Cloud Run Job実行
make batch-logs      # 実行履歴確認
```

### ローカル開発

```bash
make batch-test       # テスト実行（11件）
make batch-run-local  # ローカルでML学習実行
make batch-ui         # MLflow UI起動
```

### リセット

```bash
make reset           # 全リソース削除 & クリーン
```

### コマンド一覧

```bash
make help
```
