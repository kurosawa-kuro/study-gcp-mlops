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

data "google_container_cluster" "hybrid_search" {
  name     = var.gke_cluster_name
  location = var.region
  project  = var.project_id

  depends_on = [module.gke]
}

data "google_client_config" "default" {}

provider "kubernetes" {
  host                   = "https://${data.google_container_cluster.hybrid_search.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(data.google_container_cluster.hybrid_search.master_auth[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${data.google_container_cluster.hybrid_search.endpoint}"
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(data.google_container_cluster.hybrid_search.master_auth[0].cluster_ca_certificate)
  }
}
