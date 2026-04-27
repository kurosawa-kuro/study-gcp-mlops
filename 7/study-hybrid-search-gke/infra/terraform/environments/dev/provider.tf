provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

data "google_project" "current" {}

# ----- kubernetes / helm providers for module.kserve -----
#
# 2 段階 apply 前提:
#   1. module.gke の作成時には kubernetes/helm provider は cluster 未作成のため使えない
#      → `terraform apply -target=module.iam -target=module.data -target=module.gke` で先行作成
#   2. cluster 完成後に全体 apply — provider が下の data source から endpoint + token を引く
#
# 対象 cluster は module.gke.cluster_name / cluster_location を参照する。
#
# Phase 7 Run 5 教訓 — `destroy-all → deploy-all` で recover-wif step が
# `terraform import module.iam.google_iam_workload_identity_pool.github ...`
# を流す時、cluster 未作成 + 本 data source が `cluster not found` で fail
# → import 全体が失敗していた (kubernetes provider の初期化が data source を
# 必須としていたため)。回避策として、`var.k8s_use_data_source = false` で
# data source 読み取りごと skip し、provider を placeholder に向ける運用を
# 用意した。WIF state recovery 等の K8s API を叩かない operation 中に
# `TF_VAR_k8s_use_data_source=false` を立てると provider init を空走できる。
# 通常 (apply) は default の `true` のまま (data source 経由で動的解決)。

data "google_container_cluster" "hybrid_search" {
  count    = var.k8s_use_data_source ? 1 : 0
  name     = var.gke_cluster_name
  location = var.region
  project  = var.project_id

  depends_on = [module.gke]
}

data "google_client_config" "default" {}

locals {
  # Provider config は data source を引くか placeholder にするかを切替える。
  # 切替 = `k8s_use_data_source` var (default true)。`false` 時は cluster
  # 不在でも provider init が落ちないが、実際の K8s API call は
  # `https://kubernetes.invalid` 宛てになるため、kubernetes/helm 系の
  # resource を実 apply する step では `true` (= default) を使う必要がある。
  k8s_host = var.k8s_use_data_source ? "https://${data.google_container_cluster.hybrid_search[0].endpoint}" : "https://kubernetes.invalid"
  k8s_ca   = var.k8s_use_data_source ? base64decode(data.google_container_cluster.hybrid_search[0].master_auth[0].cluster_ca_certificate) : ""
}

provider "kubernetes" {
  host                   = local.k8s_host
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = local.k8s_ca
}

provider "helm" {
  kubernetes {
    host                   = local.k8s_host
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = local.k8s_ca
  }
}
