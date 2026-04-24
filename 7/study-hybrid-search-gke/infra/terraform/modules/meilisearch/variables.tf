variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Region for meili-search Cloud Run service"
  type        = string
}

variable "service_accounts" {
  description = "Service account map from iam module"
  type        = any
}

variable "meili_data_bucket_name" {
  description = "GCS bucket name mounted to /meili_data by Cloud Storage FUSE"
  type        = string
  default     = "mlops-dev-a-meili-data"
}

variable "meili_image" {
  description = "Container image for meilisearch service"
  type        = string
  default     = "gcr.io/cloudrun/hello"
}

variable "meili_master_key_secret_id" {
  description = "Secret Manager secret ID for MEILI_MASTER_KEY (e.g. 'meili-master-key'). Injected into the Cloud Run container via value_source.secret_key_ref."
  type        = string
  default     = "meili-master-key"
}
