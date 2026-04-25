"""``SemanticSearchPort`` adapter — BigQuery ``VECTOR_SEARCH``.

Phase 5 default. Carries attribute filter pushdown against
``properties_cleaned`` inline so one BQ job covers both retrieval and
filter (= keeps the original ``BigQueryCandidateRetriever._semantic_search``
shape).
"""

from __future__ import annotations

from google.cloud import bigquery

from app.domain.search import SearchFilters
from app.services.protocols._types import SemanticResult


class BigQuerySemanticSearch:
    """Phase 5 default — ``VECTOR_SEARCH`` over ``property_embeddings``."""

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
        filters: SearchFilters,
        top_k: int,
    ) -> list[SemanticResult]:
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
        out: list[SemanticResult] = []
        for row in rows:
            property_id = str(row["property_id"])
            semantic_rank = int(row["semantic_rank"])
            me5_score = 1.0 - float(row["cosine_distance"] or 1.0)
            out.append(
                SemanticResult(
                    property_id=property_id,
                    rank=semantic_rank,
                    similarity=me5_score,
                )
            )
        return out
