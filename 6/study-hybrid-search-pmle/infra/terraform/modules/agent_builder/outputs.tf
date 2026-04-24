output "data_store_id" {
  description = "Discovery Engine DataStore id. Use as source when ingesting property documents via DocumentService.ImportDocuments."
  value       = google_discovery_engine_data_store.properties.data_store_id
}

output "data_store_full_name" {
  description = "Fully-qualified DataStore name (projects/.../locations/.../collections/.../dataStores/...)."
  value       = google_discovery_engine_data_store.properties.name
}

output "engine_id" {
  description = "Discovery Engine SearchEngine id. Register as VERTEX_AGENT_BUILDER_ENGINE_ID on search-api."
  value       = google_discovery_engine_search_engine.properties.engine_id
}

output "engine_full_name" {
  description = "Fully-qualified Engine name (projects/.../locations/.../collections/.../engines/...)."
  value       = google_discovery_engine_search_engine.properties.name
}
