"""Semantic search adapters — ``SemanticSearchPort`` implementations.

Phase 5 ships ``BigQuerySemanticSearch`` (``VECTOR_SEARCH`` + ``LEFT JOIN``
for attribute filters). Phase 6 T3 adds ``VertexVectorSearchSemantic``
which talks to a deployed Matching Engine ``IndexEndpoint``. Both satisfy
the same Port so the rest of the search pipeline (lexical → RRF → feature
enrichment → reranker) is untouched by the swap.

Attribute filters (``max_rent`` / ``layout`` / ``max_walk_min`` / ``pet_ok``
/ ``max_age``) on the Vertex path are applied *after* Matching Engine
returns neighbours: the index itself stores only embeddings, not structured
property data, so we post-filter through BigQuery. This keeps parity with
the BQ backend's response shape.
"""

from __future__ import annotations

from typing import Any

from google.cloud import bigquery


class BigQuerySemanticSearch:
    """Phase 5 default — ``VECTOR_SEARCH`` over ``property_embeddings``.

    Carries the filter pushdown against ``properties_cleaned`` inline so one
    BQ job covers both retrieval and filter. Equivalent to the original
    ``BigQueryCandidateRetriever._semantic_search`` logic.
    """

    def __init__(
        self,
        *,
        embeddings_table: str,
        properties_table: str,
        client: bigquery.Client,
    ) -> None:
        self._embeddings_table = embeddings_table
        self._properties_table = properties_table
        self._client = client

    def search(
        self,
        *,
        query_vector: list[float],
        filters: dict[str, Any],
        top_k: int,
    ) -> list[tuple[str, int, float]]:
        query = f"""
            WITH base AS (
              SELECT
                v.base.property_id AS property_id,
                v.distance AS cosine_distance
              FROM VECTOR_SEARCH(
                TABLE `{self._embeddings_table}`,
                'embedding',
                (SELECT @query_vec AS embedding),
                top_k => @pool_size,
                distance_type => 'COSINE'
              ) v
            ),
            filtered AS (
              SELECT
                b.property_id,
                b.cosine_distance
              FROM base b
              LEFT JOIN `{self._properties_table}` p USING (property_id)
              WHERE
                (@max_rent IS NULL OR p.rent <= @max_rent)
                AND (@layout IS NULL OR p.layout = @layout)
                AND (@max_walk_min IS NULL OR p.walk_min <= @max_walk_min)
                AND (@pet_ok IS NULL OR p.pet_ok = @pet_ok)
                AND (@max_age IS NULL OR p.age_years <= @max_age)
            )
            SELECT
              property_id,
              cosine_distance,
              ROW_NUMBER() OVER (ORDER BY cosine_distance ASC) AS semantic_rank
            FROM filtered
            ORDER BY cosine_distance ASC
            LIMIT @pool_size
        """
        params = [
            bigquery.ArrayQueryParameter("query_vec", "FLOAT64", query_vector),
            bigquery.ScalarQueryParameter("pool_size", "INT64", top_k),
            bigquery.ScalarQueryParameter("max_rent", "INT64", filters.get("max_rent")),
            bigquery.ScalarQueryParameter("layout", "STRING", filters.get("layout")),
            bigquery.ScalarQueryParameter("max_walk_min", "INT64", filters.get("max_walk_min")),
            bigquery.ScalarQueryParameter("pet_ok", "BOOL", filters.get("pet_ok")),
            bigquery.ScalarQueryParameter("max_age", "INT64", filters.get("max_age")),
        ]
        rows = self._client.query(
            query, job_config=bigquery.QueryJobConfig(query_parameters=params)
        ).result()
        out: list[tuple[str, int, float]] = []
        for row in rows:
            property_id = str(row["property_id"])
            semantic_rank = int(row["semantic_rank"])
            me5_score = 1.0 - float(row["cosine_distance"] or 1.0)
            out.append((property_id, semantic_rank, me5_score))
        return out


class VertexVectorSearchSemantic:
    """Phase 6 T3 — Matching Engine ``find_neighbors`` + BQ post-filter.

    Filters must still consult ``properties_cleaned`` because the index
    carries only embeddings. Neighbour distances returned by Matching Engine
    are already in cosine units (if the index was built with
    ``distance_measure_type=COSINE_DISTANCE``); we normalise to similarity
    via ``1 - distance`` to keep the Port's ``me5_score`` contract.
    """

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
    ) -> list[tuple[str, int, float]]:
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

        # Post-filter via BQ against the same properties_cleaned source
        # BigQuerySemanticSearch uses, so the two adapters return identical
        # attribute-filter semantics.
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

        out: list[tuple[str, int, float]] = []
        rank = 1
        for property_id, cosine_distance in ranked:
            if property_id not in kept:
                continue
            similarity = 1.0 - cosine_distance
            out.append((property_id, rank, similarity))
            rank += 1
        return out
