"""``SemanticSearchPort`` adapter — Vertex AI Vector Search (Matching Engine).

Phase 6 T3 — ``find_neighbors`` against a deployed ``IndexEndpoint`` then
post-filter through BigQuery (the index stores only embeddings, not
structured property data). Distances returned by Matching Engine are
cosine when the index is built with ``distance_measure_type=COSINE_DISTANCE``;
we normalise to similarity via ``1 - distance`` to match the Port's
``me5_score`` contract.
"""

from __future__ import annotations

from typing import Any

from google.cloud import bigquery

from app.services.protocols._types import SemanticResult


class VertexVectorSearchSemantic:
    """Phase 6 T3 — Matching Engine ``find_neighbors`` + BQ post-filter."""

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        index_endpoint_id: str,
        deployed_index_id: str,
        properties_table: str,
        client: bigquery.Client,
        endpoint: Any | None = None,
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._index_endpoint_id = index_endpoint_id
        self._deployed_index_id = deployed_index_id
        self._properties_table = properties_table
        self._client = client
        self._endpoint = endpoint

    def prepare(self) -> None:
        """Eagerly construct the ``MatchingEngineIndexEndpoint`` (Phase A-4).

        Composition root calls this at startup so SDK init happens
        deterministically rather than on the first /search request.
        """
        self._matching_engine()

    def _matching_engine(self) -> Any:
        if self._endpoint is not None:
            return self._endpoint
        from google.cloud import aiplatform

        aiplatform.init(project=self._project_id, location=self._location)
        if self._index_endpoint_id.startswith("projects/"):
            resource_name = self._index_endpoint_id
        else:
            resource_name = (
                f"projects/{self._project_id}/locations/{self._location}/"
                f"indexEndpoints/{self._index_endpoint_id}"
            )
        self._endpoint = aiplatform.MatchingEngineIndexEndpoint(resource_name)
        return self._endpoint

    def search(
        self,
        *,
        query_vector: list[float],
        filters: dict[str, Any],
        top_k: int,
    ) -> list[SemanticResult]:
        endpoint = self._matching_engine()
        neighbours_batches = endpoint.find_neighbors(
            deployed_index_id=self._deployed_index_id,
            queries=[query_vector],
            num_neighbors=top_k,
        )
        neighbours = neighbours_batches[0] if neighbours_batches else []
        if not neighbours:
            return []

        # (property_id, cosine_distance) preserving Matching Engine order.
        ranked = [(str(n.id), float(getattr(n, "distance", 0.0))) for n in neighbours]
        ids = [pid for pid, _ in ranked]

        # Post-filter via BQ against the same properties_cleaned source the
        # BigQuerySemanticSearch adapter uses, so the two adapters return
        # identical attribute-filter semantics.
        filter_clause = """
            AND (@max_rent IS NULL OR p.rent <= @max_rent)
            AND (@layout IS NULL OR p.layout = @layout)
            AND (@max_walk_min IS NULL OR p.walk_min <= @max_walk_min)
            AND (@pet_ok IS NULL OR p.pet_ok = @pet_ok)
            AND (@max_age IS NULL OR p.age_years <= @max_age)
        """
        query = f"""
            SELECT p.property_id
            FROM `{self._properties_table}` p
            WHERE p.property_id IN UNNEST(@ids)
            {filter_clause}
        """
        params = [
            bigquery.ArrayQueryParameter("ids", "STRING", ids),
            bigquery.ScalarQueryParameter("max_rent", "INT64", filters.get("max_rent")),
            bigquery.ScalarQueryParameter("layout", "STRING", filters.get("layout")),
            bigquery.ScalarQueryParameter("max_walk_min", "INT64", filters.get("max_walk_min")),
            bigquery.ScalarQueryParameter("pet_ok", "BOOL", filters.get("pet_ok")),
            bigquery.ScalarQueryParameter("max_age", "INT64", filters.get("max_age")),
        ]
        rows = self._client.query(
            query, job_config=bigquery.QueryJobConfig(query_parameters=params)
        ).result()
        kept = {str(row["property_id"]) for row in rows}

        out: list[SemanticResult] = []
        rank = 1
        for property_id, cosine_distance in ranked:
            if property_id not in kept:
                continue
            similarity = 1.0 - cosine_distance
            out.append(
                SemanticResult(property_id=property_id, rank=rank, similarity=similarity)
            )
            rank += 1
        return out
