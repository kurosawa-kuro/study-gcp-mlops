variable "project_id" {
  description = "GCP project hosting the Matching Engine index + endpoint"
  type        = string
}

variable "region" {
  description = "Region for the index / endpoint. Must match var.vertex_location elsewhere (asia-northeast1 for this repo)."
  type        = string
}

variable "index_display_name" {
  description = "Display name for the Matching Engine index. Shown in the Vertex AI UI."
  type        = string
  default     = "property-vector-search-index"
}

variable "endpoint_display_name" {
  description = "Display name for the IndexEndpoint. Shown in the Vertex AI UI."
  type        = string
  default     = "property-vector-search-endpoint"
}

variable "embedding_dimensions" {
  description = "Vector dimensionality. multilingual-e5-base = 768."
  type        = number
  default     = 768
}

variable "distance_measure_type" {
  description = "Distance measure. Keep COSINE to match Phase 5 BQ VECTOR_SEARCH (distance_type=COSINE). Phase 5 stores me5_score = 1 - cosine_distance."
  type        = string
  default     = "COSINE_DISTANCE"

  validation {
    condition = contains(
      [
        "DOT_PRODUCT_DISTANCE",
        "COSINE_DISTANCE",
        "SQUARED_L2_DISTANCE",
      ],
      var.distance_measure_type,
    )
    error_message = "distance_measure_type must be one of DOT_PRODUCT_DISTANCE / COSINE_DISTANCE / SQUARED_L2_DISTANCE."
  }
}

variable "approximate_neighbors_count" {
  description = "Tree-AH approximate neighbour pool. Larger = higher recall at more CPU. 150 is the Google default for Tree-AH."
  type        = number
  default     = 150
}

variable "contents_delta_uri" {
  description = "GCS URI (gs://...) of a folder containing Matching Engine input JSONL. Empty = create an empty index; operators ingest via upsert-datapoints later. Non-empty triggers a batch build at create time."
  type        = string
  default     = ""
}

variable "enable_endpoint" {
  description = "Create google_vertex_ai_index_endpoint. Disable when only the index itself is needed (e.g. rebuild scenarios)."
  type        = bool
  default     = true
}

variable "public_endpoint_enabled" {
  description = "If true, create a public IndexEndpoint. If false, require a VPC network for private access (not wired in this module yet)."
  type        = bool
  default     = true
}
