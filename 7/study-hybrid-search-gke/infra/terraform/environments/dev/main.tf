# =========================================================================
# Root module (Phase 6: GKE + KServe) — orchestrates sub-modules:
#   iam        → Service Accounts / WIF / project-level role bindings
#   data       → BigQuery / GCS / Artifact Registry / Secret Manager + data IAM
#   vertex     → Vertex AI Pipelines / Feature Group / Model Registry (inherited from Phase 5)
#   gke        → GKE Autopilot cluster + Workload Identity bindings
#   kserve     → KServe + cert-manager + 3 KSA (api / encoder / reranker)
#   runtime    → Pub/Sub + BQ subscription + Cloud Scheduler (Cloud Run Service を持たない)
#   meilisearch→ Cloud Run Service (BM25 lexical retrieval、Phase 5 継承)
#   monitoring → log-based metrics / alert policies / mean-drift Scheduled Query
#
# Shared preconditions (API enablement) live in apis.tf and are enforced via
# `depends_on = [google_project_service.enabled]` on each module call.
#
# 2 段階 apply: 初回は `-target=module.gke -target=module.iam -target=module.data`
# で cluster / IAM / storage を作り、provider.tf で kubernetes/helm provider を
# 有効化した後に全体 apply で KServe / manifests を展開する。
# =========================================================================

module "iam" {
  source = "../../modules/iam"

  project_id  = var.project_id
  github_repo = var.github_repo

  depends_on = [google_project_service.enabled]
}

module "data" {
  source = "../../modules/data"

  project_id                        = var.project_id
  region                            = var.region
  artifact_repo_id                  = var.artifact_repo_id
  models_bucket_name                = var.models_bucket_name
  pipeline_root_bucket_name         = var.pipeline_root_bucket_name
  artifacts_bucket_name             = var.artifacts_bucket_name
  service_accounts                  = module.iam.service_accounts
  github_repo                       = var.github_repo
  dataform_repository_id            = var.dataform_repository_id
  dataform_git_token_secret_version = var.dataform_git_token_secret_version
  github_deployer_sa_email          = "sa-github-deployer@${var.project_id}.iam.gserviceaccount.com"
  enable_deletion_protection        = var.enable_deletion_protection

  depends_on = [google_project_service.enabled]
}

module "vertex" {
  source = "../../modules/vertex"

  project_id                       = var.project_id
  region                           = var.region
  vertex_location                  = var.vertex_location
  service_accounts                 = module.iam.service_accounts
  mlops_dataset_id                 = module.data.mlops_dataset.dataset_id
  feature_mart_dataset_id          = module.data.feature_mart_dataset.dataset_id
  pipeline_root_bucket_name        = module.data.pipeline_root_bucket.name
  models_bucket_name               = module.data.models_bucket.name
  model_monitoring_alerts_table_id = module.data.model_monitoring_alerts_table.table_id
  encoder_endpoint_id              = var.vertex_encoder_endpoint_id
  reranker_endpoint_id             = var.vertex_reranker_endpoint_id
  encoder_endpoint_display_name    = "property-encoder-endpoint"
  reranker_endpoint_display_name   = "property-reranker-endpoint"
  retrain_trigger_topic_id         = module.runtime.retrain_trigger_topic.id
  retrain_trigger_topic_name       = module.runtime.retrain_trigger_topic.name

  depends_on = [
    google_project_service.enabled,
    module.data,
    module.iam,
    module.runtime,
  ]
}

module "gke" {
  source = "../../modules/gke"

  project_id          = var.project_id
  region              = var.region
  cluster_name        = var.gke_cluster_name
  deletion_protection = var.enable_deletion_protection
  service_accounts    = module.iam.service_accounts

  depends_on = [
    google_project_service.enabled,
    module.iam,
  ]
}

module "kserve" {
  source = "../../modules/kserve"

  ksa_names        = module.gke.ksa_names
  service_accounts = module.iam.service_accounts

  depends_on = [
    module.gke,
  ]
}

module "runtime" {
  source = "../../modules/runtime"

  project_id               = var.project_id
  region                   = var.region
  mlops_dataset_id         = module.data.mlops_dataset.dataset_id
  ranking_log_table_id     = module.data.ranking_log_table.table_id
  feedback_events_table_id = module.data.feedback_events_table.table_id
  service_accounts         = module.iam.service_accounts
  api_external_url         = var.api_external_url

  depends_on = [
    google_project_service.enabled,
    module.data,
  ]
}

module "meilisearch" {
  source = "../../modules/meilisearch"

  project_id                 = var.project_id
  region                     = var.region
  service_accounts           = module.iam.service_accounts
  meili_data_bucket_name     = var.meili_data_bucket_name
  meili_master_key_secret_id = module.data.secrets.meili_master_key.secret_id

  depends_on = [google_project_service.enabled, module.data]
}

module "monitoring" {
  source = "../../modules/monitoring"

  project_id           = var.project_id
  region               = var.region
  mlops_dataset_id     = module.data.mlops_dataset.dataset_id
  ranker_skew_sql_path = "${path.root}/../../../../monitoring/validate_feature_skew.sql"
  oncall_email         = var.oncall_email
  service_accounts     = module.iam.service_accounts

  depends_on = [
    google_project_service.enabled,
    module.data,
  ]
}
