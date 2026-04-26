# .github/workflows — Phase 7 (CI/CD)

## ジョブ一覧

| Workflow | トリガー | 役割 |
|---|---|---|
| `ci.yml` | すべての PR / push | ruff + mypy + pytest をマトリクスで並列実行 (uv) |
| `terraform.yml` | `infra/**` | plan (PR コメント) + apply (main マージ) |
| `deploy-api.yml` | `app/**` / `common/**` | docker build → push → `gcloud run deploy search-api` |
| `deploy-training-job.yml` | `ml/training/**` / `common/**` | docker build (`infra/run/jobs/training/Dockerfile`) → push → `gcloud run jobs update training-job` |
| `deploy-embedding-job.yml` | `ml/data/**` / `common/src/common/embeddings/**` | docker build (`infra/run/jobs/embedding/Dockerfile`) → push → `gcloud run jobs update embedding-job` |
| `deploy-dataform.yml` | `definitions/**` | Dataform CLI compile + リポジトリ pull トリガー |

## 必須 GitHub Variables

Repository settings → Variables で設定:

| 名前 | 値 |
|---|---|
| `WORKLOAD_IDENTITY_PROVIDER` | `projects/<number>/locations/global/workloadIdentityPools/github/providers/github-oidc` (`terraform output workload_identity_provider` で取得) |
| `DEPLOYER_SERVICE_ACCOUNT` | `sa-github-deployer@mlops-dev-a.iam.gserviceaccount.com` |

## Secrets

**不要**。Workload Identity Federation を使うので SA Key は作らない。アプリ側のシークレット (Meilisearch master key 等) は Cloud Run の環境変数経由 (Secret Manager 参照) で注入するので CI には載せない。

## 設計上の判断

- **SA Key を作らない** (`study-gcp/study-gcp-mlops` の `credentials_json: ${{ secrets.GCP_SA_KEY }}` を捨てた理由) — セキュリティポスチャ向上と、キーローテーション不要のため。
- **path filter** で `app/**` / `ml/training/**` / `ml/data/**` を分離 — 片方の変更で他がデプロイされない。`common/**` は 3 つ全てに影響するため 3 workflow すべての filter に含める。`common/src/common/embeddings/**` は app (query encode) と embedding-job (passage encode) の共有コードで、`deploy-api.yml` / `deploy-embedding-job.yml` 双方が含める。
- **lint/typecheck/test はマトリクス並列** — 直列だとキャッシュ温存できる代わりに待ち時間が長くなるため並列優先。uv が依存を速くインストールできる前提。
- **Cloud Run の template は `ignore_changes`** で Terraform 管轄から外し、CI が `gcloud run deploy/update` で image を更新する形にドリフト防止。
