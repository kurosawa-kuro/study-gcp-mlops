output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "models_bucket" {
  value = module.data.models_bucket.name
}

output "pipeline_root_bucket" {
  description = "GCS bucket used as Vertex AI pipeline root"
  value       = module.data.pipeline_root_bucket.name
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${module.data.artifact_registry.repository_id}"
}

output "training_runs_table" {
  value = "${var.project_id}.${module.data.mlops_dataset.dataset_id}.${module.data.training_runs_table.table_id}"
}

output "ranking_log_table" {
  value = "${var.project_id}.${module.data.mlops_dataset.dataset_id}.${module.data.ranking_log_table.table_id}"
}

output "feedback_events_table" {
  value = "${var.project_id}.${module.data.mlops_dataset.dataset_id}.${module.data.feedback_events_table.table_id}"
}

output "model_monitoring_alerts_table" {
  description = "BigQuery sink for Vertex model monitoring alerts"
  value       = "${var.project_id}.${module.data.mlops_dataset.dataset_id}.${module.data.model_monitoring_alerts_table.table_id}"
}

output "ranking_log_topic" {
  value = module.runtime.ranking_log_topic.name
}

output "search_feedback_topic" {
  value = module.runtime.search_feedback_topic.name
}

output "retrain_trigger_topic" {
  value = module.runtime.retrain_trigger_topic.name
}

output "service_accounts" {
  value = {
    api               = module.iam.service_accounts.api.email
    job_train         = module.iam.service_accounts.job_train.email
    job_embed         = module.iam.service_accounts.job_embed.email
    dataform          = module.iam.service_accounts.dataform.email
    scheduler         = module.iam.service_accounts.scheduler.email
    pipeline          = module.iam.service_accounts.pipeline.email
    endpoint_encoder  = module.iam.service_accounts.endpoint_encoder.email
    endpoint_reranker = module.iam.service_accounts.endpoint_reranker.email
    pipeline_trigger  = module.iam.service_accounts.pipeline_trigger.email
  }
}

output "vertex_encoder_endpoint_name" {
  description = "Resolved Vertex encoder endpoint resource name placeholder"
  value       = module.vertex.encoder_endpoint_name
}

output "vertex_reranker_endpoint_name" {
  description = "Resolved Vertex reranker endpoint resource name placeholder"
  value       = module.vertex.reranker_endpoint_name
}

output "vertex_feature_group_property_features" {
  description = "Canonical property-side feature declarations for the Vertex Feature Group scaffold"
  value       = module.vertex.feature_group_property_features
}

output "model_monitoring_alerts_topic" {
  description = "Pub/Sub topic for Vertex model monitoring alerts"
  value       = module.vertex.model_monitoring_alerts_topic.name
}

output "model_monitoring_alerts_subscription" {
  description = "BigQuery subscription for Vertex model monitoring alerts"
  value       = module.vertex.monitoring_alerts_subscription.name
}

output "pipeline_trigger_function_name" {
  description = "Reserved Cloud Function name for the Vertex pipeline trigger"
  value       = module.vertex.pipeline_trigger_function_name
}

output "pipeline_trigger_eventarc_name" {
  description = "Reserved Eventarc trigger name for retrain-to-pipeline wiring"
  value       = module.vertex.pipeline_trigger_eventarc_name
}

output "monitoring_trigger_eventarc_name" {
  description = "Eventarc trigger name for monitoring-to-pipeline wiring"
  value       = module.vertex.monitoring_trigger_eventarc_name
}

output "workload_identity_provider" {
  description = "Register as GitHub Actions var WORKLOAD_IDENTITY_PROVIDER"
  value       = module.iam.workload_identity_provider
}

output "github_deployer_sa_email" {
  description = "Register as GitHub Actions var DEPLOYER_SERVICE_ACCOUNT"
  value       = module.iam.github_deployer_sa_email
}

output "dataform_repository_name" {
  description = "Dataform repository name — matches env.REPOSITORY in .github/workflows/deploy-dataform.yml"
  value       = module.data.dataform_repository.name
}

output "meili_base_url" {
  description = "Cloud Run URL of meili-search service"
  value       = module.meilisearch.meili_base_url
}

output "meili_data_bucket" {
  description = "GCS bucket mounted by meili-search"
  value       = module.meilisearch.meili_data_bucket.name
}

# =========================================================================
# Phase 6 T5 — SLO identifiers (used by `make ops-slo-status`).
# =========================================================================

output "slo_service_id" {
  description = "Cloud Monitoring custom-service anchoring the search-api SLOs"
  value       = module.slo.service_id
}

output "slo_availability_name" {
  description = "Full resource name of the availability SLO (projects/.../services/.../serviceLevelObjectives/...)"
  value       = module.slo.availability_slo_name
}

output "slo_latency_name" {
  description = "Full resource name of the latency SLO"
  value       = module.slo.latency_slo_name
}

# =========================================================================
# Phase 6 T3 — Matching Engine index + endpoint IDs (only populated when
# enable_vector_search=true).
# =========================================================================

output "vector_search_index_id" {
  description = "Short Matching Engine index ID (empty when enable_vector_search=false)"
  value       = var.enable_vector_search ? module.vector_search[0].index_id : ""
}

output "vector_search_index_endpoint_id" {
  description = "Short Matching Engine IndexEndpoint ID. Register as env var VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID on search-api."
  value       = var.enable_vector_search ? module.vector_search[0].index_endpoint_id : ""
}

# =========================================================================
# Phase 6 T2 — Dataflow streaming (populated only when enable_streaming=true).
# =========================================================================

output "streaming_service_account" {
  description = "sa-dataflow email. Grant Pub/Sub subscriber, BQ data editor, Storage objectAdmin."
  value       = var.enable_streaming ? module.streaming[0].service_account_email : ""
}

output "streaming_job_name" {
  description = "Dataflow streaming job name — empty unless enable_streaming_job=true."
  value       = var.enable_streaming ? module.streaming[0].job_name : ""
}

# =========================================================================
# Phase 6 T7 — Agent Builder (Discovery Engine) scaffold.
# =========================================================================

output "agent_builder_engine_id" {
  description = "Discovery Engine search engine id. Register as VERTEX_AGENT_BUILDER_ENGINE_ID on search-api."
  value       = var.enable_agent_builder ? module.agent_builder[0].engine_id : ""
}

output "agent_builder_data_store_id" {
  description = "Discovery Engine data store id (holds property documents)."
  value       = var.enable_agent_builder ? module.agent_builder[0].data_store_id : ""
}
