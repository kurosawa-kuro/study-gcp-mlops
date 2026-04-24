# Phase 6 T7 — Vertex AI Agent Builder (Discovery Engine) scaffold.
#
# Declares a DataStore + SearchEngine. Document ingestion
# (``discoveryengine_v1.DocumentService.ImportDocuments``) is out-of-band:
# operators run a one-off Python job to push property_id + searchable
# fields from BigQuery into this DataStore. The search-api side uses
# ``app/services/adapters/agent_builder_lexical.py`` to query the
# SearchEngine via serving_config ``default_search`` at opt-in time
# (``/search?lexical=agent_builder``). Meilisearch remains the primary
# lexical backend (親リポ non-negotiable).

resource "google_discovery_engine_data_store" "properties" {
  project           = var.project_id
  location          = var.location
  data_store_id     = var.data_store_id
  display_name      = var.data_store_display_name
  industry_vertical = var.industry_vertical
  solution_types    = var.solution_types
  content_config    = "NO_CONTENT"
}

resource "google_discovery_engine_search_engine" "properties" {
  project        = var.project_id
  location       = var.location
  engine_id      = var.engine_id
  display_name   = var.engine_display_name
  collection_id  = "default_collection"
  data_store_ids = [google_discovery_engine_data_store.properties.data_store_id]

  industry_vertical = var.industry_vertical

  common_config {
    company_name = "mlops-dev-a"
  }

  search_engine_config {
    search_tier    = "SEARCH_TIER_STANDARD"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }
}
