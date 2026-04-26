# =========================================================================
# Root module — orchestrates sub-modules with clear boundary:
#   iam        → Service Accounts / WIF / project-level role bindings
#   data       → BigQuery / GCS / Artifact Registry / Secret Manager + data IAM
#   runtime    → Cloud Run Service & Job / Pub/Sub / Scheduler / Eventarc + invoker IAM
#   meilisearch→ Cloud Run Service (BM25 lexical retrieval) + GCS FUSE data mount
#   monitoring → log-based metrics / alert policies / mean-drift Scheduled Query
#
# Shared preconditions (API enablement) live in apis.tf and are enforced via
# `depends_on = [google_project_service.enabled]` on each module call.
# =========================================================================

module "iam" {
  source = "../../modules/iam"

  project_id        = var.project_id
  github_repo       = var.github_repo
  admin_user_emails = var.admin_user_emails

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
  # Deterministic form (not module.iam.github_deployer_sa_email) so the data
  # module's `count = ... != "" ? 1 : 0` can be evaluated at plan time. The SA
  # is still created by module.iam; ordering is preserved via the
  # `service_accounts` reference above, which establishes an implicit dep.
  github_deployer_sa_email   = "sa-github-deployer@${var.project_id}.iam.gserviceaccount.com"
  enable_deletion_protection = var.enable_deletion_protection

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

module "runtime" {
  source = "../../modules/runtime"

  project_id                  = var.project_id
  region                      = var.region
  artifact_repo_id            = var.artifact_repo_id
  models_bucket_name          = module.data.models_bucket.name
  mlops_dataset_id            = module.data.mlops_dataset.dataset_id
  feature_mart_dataset_id     = module.data.feature_mart_dataset.dataset_id
  ranking_log_table_id        = module.data.ranking_log_table.table_id
  feedback_events_table_id    = module.data.feedback_events_table.table_id
  service_accounts            = module.iam.service_accounts
  meili_base_url              = module.meilisearch.meili_base_url
  search_cache_ttl_seconds    = var.search_cache_ttl_seconds
  vertex_location             = var.vertex_location
  vertex_encoder_endpoint_id  = var.vertex_encoder_endpoint_id
  vertex_reranker_endpoint_id = var.vertex_reranker_endpoint_id

  depends_on = [
    google_project_service.enabled,
    module.data,
    module.meilisearch,
  ]
}

module "meilisearch" {
  source = "../../modules/meilisearch"

  project_id             = var.project_id
  region                 = var.region
  service_accounts       = module.iam.service_accounts
  meili_data_bucket_name = var.meili_data_bucket_name

  depends_on = [google_project_service.enabled]
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

# Phase 6 T2 — Dataflow streaming job scaffold (ranking-log hourly CTR).
# The Flex Template image + spec JSON are built out of band; module
# creates sa-dataflow + IAM. Flip enable_streaming_job=true after the
# template is in GCS to register the streaming job itself.
module "streaming" {
  count  = var.enable_streaming ? 1 : 0
  source = "../../modules/streaming"

  project_id             = var.project_id
  region                 = var.region
  ranking_log_topic_id   = module.runtime.ranking_log_topic.id
  output_table_fqn       = "${var.project_id}:${module.data.mlops_dataset.dataset_id}.${module.data.ranking_log_hourly_ctr_table.table_id}"
  flex_template_gcs_path = var.streaming_flex_template_gcs_path
  temp_location          = "gs://${module.data.artifacts_bucket.name}/dataflow/tmp"
  staging_location       = "gs://${module.data.artifacts_bucket.name}/dataflow/staging"
  create_job             = var.enable_streaming_job

  depends_on = [
    google_project_service.enabled,
    module.data,
    module.runtime,
  ]
}

# Phase 6 T5 — formal SLOs (availability + latency) + burn-rate alerts on
# search-api Cloud Run. Reuses the notification channel created by
# module.monitoring so operators do not receive duplicate emails.
module "slo" {
  source = "../../modules/slo"

  project_id               = var.project_id
  region                   = var.region
  service_name             = "search-api"
  notification_channel_ids = [module.monitoring.notification_channel_id]

  availability_goal    = var.slo_availability_goal
  latency_threshold_ms = var.slo_latency_threshold_ms
  latency_goal         = var.slo_latency_goal
  rolling_period_days  = var.slo_rolling_period_days

  depends_on = [
    google_project_service.enabled,
    module.monitoring,
    module.runtime,
  ]
}
