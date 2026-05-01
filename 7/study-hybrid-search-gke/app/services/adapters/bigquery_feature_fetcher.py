"""``FeatureFetcher`` adapter — BigQuery direct read (Phase 7 PR-2).

Phase 4 default path. Reads the same ``property_features_daily`` view that
``BigQueryCandidateRetriever._enrich_from_bq`` joins inline today, but
extracted as a stand-alone Port implementation so callers (PR-4: KServe
reranker) can swap to Feature Online Store without touching the retriever.

Latency:
    A single ``SELECT ... WHERE property_id IN UNNEST(@ids)`` round-trip
    against BigQuery, with the latest event_date filter inline. Adequate
    for offline / batch eval; production /search uses the FOS adapter.
"""

from __future__ import annotations

from google.cloud import bigquery

from app.services.protocols.feature_fetcher import FeatureRow


class BigQueryFeatureFetcher:
    """Phase 4 default — BigQuery scan over ``property_features_daily``.

    Args:
        features_table: Fully-qualified ``project.dataset.table`` for
            ``feature_mart.property_features_daily``.
        client: pre-built ``bigquery.Client`` (centralized lifecycle).
    """

    def __init__(
        self,
        *,
        features_table: str,
        client: bigquery.Client,
    ) -> None:
        if not features_table:
            raise ValueError("features_table is required")
        self._features_table = features_table
        self._client = client

    def fetch(self, property_ids: list[str]) -> dict[str, FeatureRow]:
        if not property_ids:
            return {}
        query = f"""
            WITH latest AS (
              SELECT *
              FROM `{self._features_table}`
              WHERE event_date = (SELECT MAX(event_date) FROM `{self._features_table}`)
            )
            SELECT
              s.property_id,
              l.ctr,
              l.fav_rate,
              l.inquiry_rate
            FROM UNNEST(@property_ids) AS s_property_id
            CROSS JOIN UNNEST([STRUCT(s_property_id AS property_id)]) AS s
            LEFT JOIN latest l USING (property_id)
        """
        params = [bigquery.ArrayQueryParameter("property_ids", "STRING", property_ids)]
        rows = self._client.query(
            query, job_config=bigquery.QueryJobConfig(query_parameters=params)
        ).result()
        out: dict[str, FeatureRow] = {}
        seen: set[str] = set()
        for row in rows:
            property_id = str(row["property_id"])
            seen.add(property_id)
            out[property_id] = FeatureRow(
                property_id=property_id,
                ctr=_as_float_or_none(row["ctr"]),
                fav_rate=_as_float_or_none(row["fav_rate"]),
                inquiry_rate=_as_float_or_none(row["inquiry_rate"]),
            )
        # Guarantee one entry per requested id (missing → all-None) so callers
        # can distinguish "fetched, no data" from "not fetched".
        for pid in property_ids:
            if pid not in seen:
                out[pid] = FeatureRow(property_id=pid, ctr=None, fav_rate=None, inquiry_rate=None)
        return out


def _as_float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(value)  # type: ignore[arg-type]
