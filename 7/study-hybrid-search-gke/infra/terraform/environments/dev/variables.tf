variable "project_id" {
  type    = string
  default = "mlops-dev-a"
}

variable "region" {
  type    = string
  default = "asia-northeast1"
}

variable "artifact_repo_id" {
  type    = string
  default = "mlops"
}

variable "models_bucket_name" {
  type    = string
  default = "mlops-dev-a-models"
}

variable "pipeline_root_bucket_name" {
  description = "GCS bucket name for Vertex AI pipeline root artifacts and compiled templates"
  type        = string
  default     = "mlops-dev-a-pipeline-root"
}

variable "meili_data_bucket_name" {
  description = "GCS bucket name mounted by meili-search"
  type        = string
  default     = "mlops-dev-a-meili-data"
}

variable "artifacts_bucket_name" {
  type    = string
  default = "mlops-dev-a-artifacts"
}

variable "github_repo" {
  description = "GitHub repository (owner/name) trusted by Workload Identity Federation + used for Dataform git_remote_settings"
  type        = string
  default     = "your-org/study-gcp-mlops-hybrid-search-cloud"
}

variable "admin_user_emails" {
  description = "Developer user account emails that need to impersonate sa-api for local one-off ops (e.g. Meilisearch document sync that requires OIDC token with audience=meili-search URL). Empty list disables the binding. Forwarded to module.iam."
  type        = list(string)
  default     = []
}

variable "dataform_repository_id" {
  description = "Dataform repository name. Must match .github/workflows/deploy-dataform.yml env.REPOSITORY"
  type        = string
  default     = "hybrid-search-cloud"
}

variable "dataform_git_token_secret_version" {
  description = "Secret Manager resource ID for the GitHub PAT Dataform uses to sync definitions/. Empty = no remote sync (use Dataform UI or CI-driven compilationResults only)"
  type        = string
  default     = ""
}

variable "oncall_email" {
  description = "Email notified by log-based alert policies. Required — must be supplied via -var='oncall_email=...' or tfvars at apply time. No default is provided on purpose (avoid shipping placeholder addresses)."
  type        = string

  validation {
    condition     = length(var.oncall_email) > 0 && can(regex("@", var.oncall_email))
    error_message = "oncall_email must be a non-empty address containing '@'."
  }
}

variable "enable_deletion_protection" {
  description = "Toggle BQ table deletion_protection across the data module. Default true (production-safe). `make destroy-all` runs `terraform apply -var=enable_deletion_protection=false` first so the subsequent destroy can proceed (Terraform refuses to destroy a table whose state still says deletion_protection=true)."
  type        = bool
  default     = true
}

variable "vertex_location" {
  description = "Vertex AI location for Pipelines / Feature Group / Model Registry (inherited from Phase 5)"
  type        = string
  default     = "asia-northeast1"
}

variable "vertex_encoder_endpoint_id" {
  description = "Vertex AI encoder endpoint ID (legacy — retained for Phase 5 compatibility; Phase 7 uses KServe)"
  type        = string
  default     = ""
}

variable "vertex_reranker_endpoint_id" {
  description = "Vertex AI reranker endpoint ID (legacy — retained for Phase 5 compatibility; Phase 7 uses KServe)"
  type        = string
  default     = ""
}

variable "gke_cluster_name" {
  description = "GKE Autopilot cluster name for Phase 7 serving"
  type        = string
  default     = "hybrid-search"
}

variable "api_external_url" {
  description = "Public HTTPS URL of search-api GKE Gateway. Leave empty on initial apply; fill after Gateway has provisioned and re-apply to materialize Cloud Scheduler."
  type        = string
  default     = ""
}

# =========================================================================
# Phase 6 T5 — SLO tunables forwarded to module.slo.
# =========================================================================

variable "slo_availability_goal" {
  description = "Availability SLO target for search-api (fraction 0-1). Default 0.99; raise after burn-rate data justifies it."
  type        = number
  default     = 0.99
}

variable "slo_latency_threshold_ms" {
  description = "Latency SLO threshold (milliseconds). Requests completing under this count as 'good'. Default 500ms mirrors the existing p95 alert."
  type        = number
  default     = 500
}

variable "slo_latency_goal" {
  description = "Fraction of requests that must complete under slo_latency_threshold_ms. Default 0.95 (p95 target)."
  type        = number
  default     = 0.95
}

variable "slo_rolling_period_days" {
  description = "Rolling window for both SLOs. Default 28 days (avoids month-boundary edge cases vs 30)."
  type        = number
  default     = 28
}

# =========================================================================
# Phase 6 T2 — Dataflow streaming toggles.
# =========================================================================

variable "enable_streaming" {
  description = "Provision the Dataflow streaming module (sa-dataflow + IAM). Default false; flip to true after ranking-log has meaningful traffic."
  type        = bool
  default     = false
}

variable "enable_streaming_job" {
  description = "Actually launch the Flex Template streaming job. Requires enable_streaming=true AND streaming_flex_template_gcs_path to be non-empty (= template already built)."
  type        = bool
  default     = false
}

variable "streaming_flex_template_gcs_path" {
  description = "GCS path to the compiled Flex Template spec JSON (built out-of-band by scripts/setup/build_streaming_template.py). Empty suppresses the Dataflow job resource."
  type        = string
  default     = ""
}

# =========================================================================
# Vertex AI Feature Online Store toggle (Phase 7 — vertex_feature_group.py).
# =========================================================================

variable "enable_feature_online_store" {
  description = "Provision the Vertex AI Feature Online Store + FeatureView so /vertex_feature_group.py fetches return featureValues. Default false because the Online Store charges per online query + node hours; flip on when exercising the script."
  type        = bool
  default     = false
}
