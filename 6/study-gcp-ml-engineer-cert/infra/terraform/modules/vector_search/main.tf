# Phase 6 T3 — Vertex AI Vector Search (Matching Engine) index + endpoint.
#
# This module declares the *scaffold* for an alternative semantic backend
# that lives alongside the Phase 5 BigQuery VECTOR_SEARCH path. The running
# /search endpoint still uses BigQuery by default (semantic_backend="bq");
# flipping SEMANTIC_BACKEND=vertex + pointing at the endpoint IDs emitted
# by this module routes semantic retrieval through Matching Engine.
#
# Scope intentionally stops at (index, endpoint). Deploying the index onto
# the endpoint is delegated to ``scripts/local/setup/deploy_vector_search.py``
# because:
#   1. First-time deployment takes 30–60min; Terraform apply should not
#      block on that.
#   2. Once the index is embedded + uploaded, deploying it is a one-time
#      act mirroring Phase 5's encoder/reranker endpoint handling.
#
# Keeps the cost profile learning-reasonable: one e2-standard-2 replica
# with min_replica_count = max_replica_count = 1 when the operator runs
# the deploy script (see scripts/local/setup/deploy_vector_search.py).

resource "google_vertex_ai_index" "property_embeddings" {
  project      = var.project_id
  region       = var.region
  display_name = var.index_display_name
  description  = "Phase 6 T3 — ME5-base 768d property embeddings (alternative to BQ VECTOR_SEARCH)."

  metadata {
    contents_delta_uri = var.contents_delta_uri
    config {
      dimensions                  = var.embedding_dimensions
      approximate_neighbors_count = var.approximate_neighbors_count
      distance_measure_type       = var.distance_measure_type
      shard_size                  = "SHARD_SIZE_SMALL"

      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }

  index_update_method = "BATCH_UPDATE"

  # Rebuilding an index takes 30+ min; Terraform should not drift the
  # contents_delta_uri after initial load.
  lifecycle {
    ignore_changes = [
      metadata[0].contents_delta_uri,
    ]
  }
}

resource "google_vertex_ai_index_endpoint" "property_search" {
  count = var.enable_endpoint ? 1 : 0

  project      = var.project_id
  region       = var.region
  display_name = var.endpoint_display_name
  description  = "Phase 6 T3 — public IndexEndpoint exposing property_embeddings for /search semantic lookup."

  # Matching Engine requires exactly one of public / private network
  # config. This module only supports public today; private VPC wiring is
  # called out in docs/02_移行ロードマップ.md for future work.
  public_endpoint_enabled = var.public_endpoint_enabled
}
