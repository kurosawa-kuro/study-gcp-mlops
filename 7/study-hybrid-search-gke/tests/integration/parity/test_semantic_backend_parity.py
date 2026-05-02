"""Live GCP parity: BigQuery semantic search vs Vertex Vector Search.

These tests are intentionally marker-gated. They provide the executable
shape for W2-7-c while remaining harmless in local/offline CI.
"""

from __future__ import annotations

import os

import pytest
from google.cloud import bigquery

from app.services.adapters.bigquery_semantic_search import BigQuerySemanticSearch
from app.services.adapters.vertex_vector_search_semantic_search import (
    VertexVectorSearchSemanticSearch,
)

pytestmark = pytest.mark.live_gcp


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"live_gcp parity requires env {name}")
    return value


def _query_vector() -> list[float]:
    raw = os.environ.get("LIVE_GCP_ME5_QUERY_VECTOR", "").strip()
    if not raw:
        pytest.skip("set LIVE_GCP_ME5_QUERY_VECTOR to a comma-separated 768d vector")
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if len(values) != 768:
        pytest.skip(f"LIVE_GCP_ME5_QUERY_VECTOR must contain 768 floats, got {len(values)}")
    return values


def test_bigquery_and_vvs_overlap_on_top_k_live() -> None:
    project_id = _env("PROJECT_ID")
    location = _env("VERTEX_LOCATION")
    query_vector = _query_vector()
    embeddings_table = _env("LIVE_GCP_EMBEDDINGS_TABLE")
    properties_table = _env("LIVE_GCP_PROPERTIES_TABLE")
    index_endpoint_name = _env("VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID")
    deployed_index_id = _env("VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID")

    bq_search = BigQuerySemanticSearch(
        embeddings_table=embeddings_table,
        properties_table=properties_table,
        client=bigquery.Client(project=project_id),
    )
    vvs_search = VertexVectorSearchSemanticSearch(
        index_endpoint_name=index_endpoint_name,
        deployed_index_id=deployed_index_id,
        project=project_id,
        location=location,
    )

    top_k = int(os.environ.get("LIVE_GCP_PARITY_TOP_K", "10"))
    filters: dict[str, object] = {}
    bq_ids = [
        row.property_id
        for row in bq_search.search(query_vector=query_vector, filters=filters, top_k=top_k)
    ]
    vvs_ids = [row.property_id for row in vvs_search.search(query_vector=query_vector, top_k=top_k)]

    assert bq_ids, "BigQuery semantic search returned no candidates"
    assert vvs_ids, "Vertex Vector Search returned no candidates"

    overlap = len(set(bq_ids) & set(vvs_ids))
    min_overlap = int(os.environ.get("LIVE_GCP_MIN_OVERLAP", "3"))
    assert overlap >= min_overlap, (
        f"semantic parity too low: overlap={overlap}, min_overlap={min_overlap}, "
        f"bq_top_k={bq_ids}, vvs_top_k={vvs_ids}"
    )
