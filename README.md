
# study-gcp

---

## 1. 目的

```text
MLopsをCloud Runベースで理解・実装する

・Kubernetesを使わない構成でMLパイプラインを構築する
・バッチ処理主体のMLフロー（学習・評価）を確立する
・推論APIまで含めた一連の流れを実装する
```

---

## 2. 技術スタック

```text
■ GCP
- Cloud Run（Job / Service）
- GCS
- BigQuery
- Artifact Registry

■ ML
- scikit-learn（HousePredict）
- MLflow（評価・ログ）

■ API
- FastAPI

■ IaC
- Terraform

CICD
Github Actoins

■ （将来）
- Vertex AI（後から置き換え）
```

※ Snowflakeは初期フェーズでは使用しない

---

## 3. アーキテクチャ

```text
[GCS raw]
   ↓
[Cloud Run Job（batch）]
   ・pandas
   ・特徴量生成
   ・scikit-learn
   ・MLflow記録
   ↓
[GCS models]

同時に
↓
[BigQuery]
・features
・metrics
・predictions

----------------------------

[Cloud Run Service（API）]
   ↓
[GCS models] をロード
   ↓
推論レスポンス（FastAPI）
```

---

## 4. ディレクトリ構成

```text
study-gcp/
├── src/
│   ├── batch/          # Cloud Run Job（学習・集計）
│   └── api/            # Cloud Run Service（FastAPI）（将来）
├── terraform/          # インフラ定義（Terraform）
├── makefiles/          # Makefile分割ファイル
├── scripts/            # セットアップ・デプロイスクリプト
├── docs/               # 手順書・ドキュメント
├── data/               # ローカル検証用
├── notebooks/          # 任意
├── Makefile            # ビルド・デプロイコマンド
└── README.md
```

---

## 5. 各レイヤの役割

### terraform/

```text
・Artifact Registry
・Cloud Run（Job / Service）
・GCS（raw / processed / models）（将来）
・BigQuery dataset（将来）
```

---

### src/batch/（Cloud Run Job）

```text
役割：
データ → 特徴量 → 学習 → 評価

フロー：
GCS → pandas → 特徴量作成 → scikit-learn → MLflow記録
→ GCSへモデル保存 → BigQueryへ評価結果保存
```

---

### src/api/（Cloud Run Service）

```text
役割：推論API
・GCSからモデルロード
・推論結果を返す（FastAPI）
※ 初期はDB接続不要
```

---

## 6. データ構造

```text
GCS
├── raw/
├── processed/
└── models/

BigQuery
- features
- predictions
- metrics
```

---

## 7. MLflowの位置づけ

```text
・パラメータ / メトリクス記録
・モデル管理
※ 実行基盤ではない

初期：ローカル or Cloud Run内（SQLite or GCS backend）
```

---

## 8. ロードマップ

```text
Phase1：ローカルで学習（pandas + sklearn）
Phase2：Docker化
Phase3：Cloud Run Job化（batch）
Phase4：MLflow導入
Phase5：API（FastAPI + Cloud Run Service）
Phase6：Terraformで全体管理
Phase7：Vertex AI検討
```

---

## 9. 使い方

### 初回セットアップ

```bash
./scripts/setup-gcp.sh        # GCP CLIインストール
./scripts/setup-terraform.sh   # Terraformインストール
gcloud init                    # GCPログイン & プロジェクト設定
make gcp-setup-apis            # 必要なAPI有効化
make gcp-setup-docker          # Docker認証設定
```

### デプロイ & 実行

```bash
make deploy          # 全体デプロイ（インフラ + batch）
make batch-run       # Job実行
make batch-logs      # 実行履歴確認
```

### リセット

```bash
make reset           # 全リソース削除 & クリーン
```

### コマンド一覧

```bash
make help
```
