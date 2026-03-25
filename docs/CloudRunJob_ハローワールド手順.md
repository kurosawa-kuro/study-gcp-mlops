# ゴール: Cloud Run JobでPython ハローワールド

## ステップ一覧

- [x] 1. GCPアカウント作成
- [x] 2. GCP CLIインストール・ログイン
- [x] 3. プロジェクト作成 `mlops-dev-a`
- [x] 4. Artifact Registry API有効化
- [x] 5. Artifact Registryリポジトリ作成（`myrepo` / `asia-northeast1` / Docker形式）
- [x] 6. Pythonスクリプト作成（Hello World）
- [x] 7. Dockerfile作成
- [x] 8. Dockerイメージビルド & Artifact Registryへpush
- [x] 9. Cloud Run Job作成・実行

## 手順

### 1〜3. GCPセットアップ（完了）

```bash
gcloud init
# プロジェクト: mlops-dev-a
# アカウント: kurokawa81toshifumi@gmail.com
```

### 4. Artifact Registry API有効化

```bash
gcloud services enable artifactregistry.googleapis.com
```

### 5. Artifact Registryリポジトリ作成

```bash
gcloud artifacts repositories create myrepo \
  --repository-format=docker \
  --location=asia-northeast1 \
  --description="MLOps Docker repository"
```

### 6. Pythonスクリプト作成

`src/batch/main.py`:

```python
print("Hello from Cloud Run Job!")
```

### 7. Dockerfile作成

`src/batch/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY main.py .
CMD ["python", "main.py"]
```

### 8. Dockerイメージビルド & push

```bash
# Docker認証設定
gcloud auth configure-docker asia-northeast1-docker.pkg.dev

# ビルド & push
docker build -t asia-northeast1-docker.pkg.dev/mlops-dev-a/myrepo/hello-job:latest ./src/batch/
docker push asia-northeast1-docker.pkg.dev/mlops-dev-a/myrepo/hello-job:latest
```

### 9. Cloud Run Job作成・実行

```bash
# Cloud Run API有効化
gcloud services enable run.googleapis.com

# Job作成
gcloud run jobs create hello-job \
  --image=asia-northeast1-docker.pkg.dev/mlops-dev-a/myrepo/hello-job:latest \
  --region=asia-northeast1

# 実行
gcloud run jobs execute hello-job --region=asia-northeast1

# ログ確認
gcloud run jobs executions list --job=hello-job --region=asia-northeast1
```