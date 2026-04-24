output "index_id" {
  description = "Short numeric index ID. Use this when passing to the deploy script or to upsert-datapoints."
  value       = google_vertex_ai_index.property_embeddings.name
}

output "index_full_name" {
  description = "Full resource name (projects/.../locations/.../indexes/...) of the Matching Engine index."
  value       = google_vertex_ai_index.property_embeddings.id
}

output "index_endpoint_id" {
  description = "Short IndexEndpoint ID for env var VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID. Empty when enable_endpoint=false."
  value       = var.enable_endpoint ? google_vertex_ai_index_endpoint.property_search[0].name : ""
}

output "index_endpoint_full_name" {
  description = "Full resource name (projects/.../locations/.../indexEndpoints/...) of the IndexEndpoint."
  value       = var.enable_endpoint ? google_vertex_ai_index_endpoint.property_search[0].id : ""
}
