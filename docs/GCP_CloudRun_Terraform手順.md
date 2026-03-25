# GCP Cloud Run + Terraform 構築手順

## ゴール

Terraformで以下を管理する:
- Artifact Registry
- Cloud Run Job（batch）
- Cloud Run Service（API）（将来）

---

## 前提

- [x] GCPプロジェクト `mlops-dev-a` 作成済み
- [x] gcloud CLI ログイン済み
- [ ] Terraform インストール
- [ ] Terraformで管理するリソースの作成

---

## ステップ一覧

- [ ] 1. Terraform インストール
- [ ] 2. サービスアカウント作成
- [ ] 3. Terraform初期設定（provider / backend）
- [ ] 4. Artifact Registry定義
- [ ] 5. Cloud Run Job定義
- [ ] 6. terraform apply で反映
- [ ] 7. 動作確認

---

## 手順

### 1. Terraform インストール

```bash
# HashiCorp GPGキー追加
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

# リポジトリ追加
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/hashicorp.list

# インストール
sudo apt-get update && sudo apt-get install -y terraform

# 確認
terraform version
```

### 2. サービスアカウント作成

Terraformがリソースを操作するためのサービスアカウントを作成する。

```bash
# サービスアカウント作成
gcloud iam service-accounts create terraform \
  --display-name="Terraform" \
  --project=mlops-dev-a

# 必要なロール付与
gcloud projects add-iam-policy-binding mlops-dev-a \
  --member="serviceAccount:terraform@mlops-dev-a.iam.gserviceaccount.com" \
  --role="roles/editor"

# キー発行（ローカル実行用）
gcloud iam service-accounts keys create ./terraform/credentials.json \
  --iam-account=terraform@mlops-dev-a.iam.gserviceaccount.com
```

> credentials.json は `.gitignore` に追加すること

### 3. Terraform初期設定

`terraform/provider.tf`:

```hcl
terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project     = var.project_id
  region      = var.region
  credentials = file("credentials.json")
}
```

`terraform/variables.tf`:

```hcl
variable "project_id" {
  default = "mlops-dev-a"
}

variable "region" {
  default = "asia-northeast1"
}

variable "repo_name" {
  default = "myrepo"
}
```

### 4. Artifact Registry定義

`terraform/artifact_registry.tf`:

```hcl
resource "google_artifact_registry_repository" "myrepo" {
  location      = var.region
  repository_id = var.repo_name
  format        = "DOCKER"
  description   = "MLOps Docker repository"
}
```

### 5. Cloud Run Job定義

`terraform/cloud_run_job.tf`:

```hcl
resource "google_cloud_run_v2_job" "hello_job" {
  name     = "hello-job"
  location = var.region

  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_name}/hello-job:latest"
      }
    }
  }

  depends_on = [google_artifact_registry_repository.myrepo]
}
```

### 6. terraform apply

```bash
cd terraform/

# 初期化
terraform init

# 差分確認
terraform plan

# 反映
terraform apply
```

### 7. 動作確認

```bash
# Cloud Run Job実行
gcloud run jobs execute hello-job \
  --region=asia-northeast1 \
  --project=mlops-dev-a

# 実行結果確認
gcloud run jobs executions list \
  --job=hello-job \
  --region=asia-northeast1 \
  --project=mlops-dev-a
```

---

## 注意事項

- 既に手動で作成済みのリソース（myrepo, hello-job）をTerraformに取り込むには `terraform import` を使う
- credentials.json は絶対にGitにコミットしない
- 本番ではサービスアカウントキーではなく Workload Identity を使うべき

### import例（既存リソース取り込み）

```bash
cd terraform/

# Artifact Registry
terraform import google_artifact_registry_repository.myrepo \
  projects/mlops-dev-a/locations/asia-northeast1/repositories/myrepo

# Cloud Run Job
terraform import google_cloud_run_v2_job.hello_job \
  projects/mlops-dev-a/locations/asia-northeast1/jobs/hello-job
```
