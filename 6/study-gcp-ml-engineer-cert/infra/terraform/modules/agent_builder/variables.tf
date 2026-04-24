variable "project_id" {
  description = "GCP project hosting the Discovery Engine datastore + engine."
  type        = string
}

variable "location" {
  description = "Discovery Engine collection location. Most surfaces are only available in ``global`` as of 2026-04."
  type        = string
  default     = "global"
}

variable "data_store_id" {
  description = "Discovery Engine DataStore id. Lowercase alphanumerics + hyphens; short strings preferred."
  type        = string
  default     = "properties-datastore"
}

variable "data_store_display_name" {
  description = "Display name shown in the Agent Builder console."
  type        = string
  default     = "properties-datastore"
}

variable "engine_id" {
  description = "Discovery Engine SearchApp / Engine id. Passed to AgentBuilderLexicalRetriever."
  type        = string
  default     = "properties-search"
}

variable "engine_display_name" {
  description = "Display name for the Search Engine."
  type        = string
  default     = "properties-search"
}

variable "industry_vertical" {
  description = "Discovery Engine industry_vertical. ``GENERIC`` keeps this learning-scope; other values enable domain-specific tuning (e.g. RETAIL / HEALTHCARE)."
  type        = string
  default     = "GENERIC"

  validation {
    condition     = contains(["GENERIC", "MEDIA", "HEALTHCARE_FHIR"], var.industry_vertical)
    error_message = "industry_vertical must be GENERIC / MEDIA / HEALTHCARE_FHIR (other verticals require Google allowlist)."
  }
}

variable "solution_types" {
  description = "Which Agent Builder solution surfaces the engine binds to. SEARCH is the only one wired here."
  type        = list(string)
  default     = ["SOLUTION_TYPE_SEARCH"]
}
