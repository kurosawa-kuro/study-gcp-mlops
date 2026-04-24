variable "kserve_version" {
  description = "KServe chart version to install via Helm"
  type        = string
  default     = "v0.14.0"
}

variable "cert_manager_version" {
  description = "cert-manager version (KServe prerequisite)"
  type        = string
  default     = "v1.15.3"
}

variable "knative_version" {
  description = "Knative Serving version (KServe Serverless mode prerequisite). Empty skips install."
  type        = string
  default     = ""
}

variable "inference_namespace" {
  description = "Namespace for KServe InferenceService resources"
  type        = string
  default     = "kserve-inference"
}

variable "search_namespace" {
  description = "Namespace for search-api workload"
  type        = string
  default     = "search"
}

variable "ksa_names" {
  description = "KSA names created in each namespace (bound to GCP SAs via Workload Identity annotation)"
  type = object({
    api      = string
    encoder  = string
    reranker = string
  })
}

variable "service_accounts" {
  description = "GCP service accounts (from iam module) for Workload Identity annotations"
  type        = any
}
