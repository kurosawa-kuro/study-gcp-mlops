"""Smoke-test Vertex AI Vector Search by issuing a nearest-neighbor query.

Verifies the deployed index responds to a query embedding (zeros vector
of `EMBEDDING_DIM` floats) — confirming ``vertex_vector_search_index_endpoint_id``
and ``vertex_vector_search_deployed_index_id`` env are both pointing to a
live index. The Phase 6 / 7 ``VertexVectorSearchSemantic`` adapter falls
back silently to BigQuery VECTOR_SEARCH on failure, so this script is the
direct way to catch a Vector Search misconfiguration.

Usage::

    VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID=...
    VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID=...
    make ops-vertex-vector-search

Exit codes:
    0  — query returned ≥ 1 neighbor
    1  — config missing or query returned zero neighbors
"""

from __future__ import annotations

import os

from scripts._common import env, fail


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("VERTEX_LOCATION", env("REGION", "asia-northeast1"))
    endpoint_id = env("VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID")
    deployed_id = env("VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID")
    embedding_dim = int(os.environ.get("EMBEDDING_DIM", "768"))
    top_k = int(os.environ.get("TOP_K", "5"))

    if not (project_id and endpoint_id and deployed_id):
        return fail(
            "vertex-vector-search: PROJECT_ID / VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID / "
            "VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID required"
        )

    from google.cloud import aiplatform

    aiplatform.init(project=project_id, location=region)

    try:
        endpoint = aiplatform.MatchingEngineIndexEndpoint(endpoint_id)
        # Use a zero vector as a probe — every index should at least
        # return its closest neighbours regardless of input direction.
        results = endpoint.find_neighbors(
            deployed_index_id=deployed_id,
            queries=[[0.0] * embedding_dim],
            num_neighbors=top_k,
        )
    except Exception as exc:
        return fail(f"vertex-vector-search: query failed: {exc}")

    if not results or not results[0]:
        return fail(
            "vertex-vector-search: query returned 0 neighbors. "
            "Index may be empty (no vectors uploaded) or deployed_index_id mismatched."
        )

    print(f"vertex-vector-search PASS: top_k={top_k} neighbors returned")
    for nb in results[0][:top_k]:
        print(f"  id={getattr(nb, 'id', '-')} distance={getattr(nb, 'distance', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
