# K8s manifests (Phase 6)

`infra/terraform/modules/{gke,kserve}` が作ったクラスタに、アプリケーション
層（`search-api` + KServe `InferenceService`）を `kubectl apply -k .` で
展開する。Terraform は cluster + KServe Operator + cert-manager + 3 KSA まで
面倒を見るが、個別ワークロードは manifests でバージョン管理する（CI での
ロールバック容易性のため）。

## ディレクトリ

- `search-api/` — FastAPI サービス (Deployment / Service / HPA / Gateway / HTTPRoute / NetworkPolicy / PodMonitoring / IAP BackendConfig / ConfigMap サンプル)
- `kserve/` — KServe InferenceService (encoder / reranker) + NetworkPolicy + PodMonitoring
- `kustomization.yaml` — 全リソースを一括 apply する Kustomize root

## デプロイ

```bash
# 1. 事前に Terraform apply で cluster + KServe Operator を作る
cd infra/terraform/environments/dev && terraform apply

# 2. kubeconfig 取得
gcloud container clusters get-credentials hybrid-search \
  --region asia-northeast1 --project mlops-dev-a

# 3. ConfigMap は env overlay or 明示的に作る (kustomization の example を書き換え or 差分 kustomize)
kubectl apply -k infra/manifests/

# 4. encoder / reranker モデルは Vertex Model Registry から同期
uv run python scripts/local/deploy/kserve_models.py

# 5. search-api イメージは scripts/local/deploy/api_gke.py で差し替え
uv run python scripts/local/deploy/api_gke.py
```

## overlay が必要な箇所

- `search-api/gateway.yaml` の `hostname` (実際の DNS 名)
- `search-api/configmap.example.yaml` の `meili_base_url` (Meilisearch の Cloud Run URL)
- `kserve/encoder.yaml` / `kserve/reranker.yaml` の `storageUri` / `image`
  (scripts/local/deploy/kserve_models.py が自動更新)
