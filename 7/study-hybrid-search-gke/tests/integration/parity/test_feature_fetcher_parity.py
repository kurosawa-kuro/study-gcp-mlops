"""Live GCP parity: BigQuery feature fetch vs Feature Online Store fetch.

Marker-gated scaffold for W2-7-c. Local/offline runs skip automatically.
"""

from __future__ import annotations

import os

import pytest
from google.cloud import bigquery

from app.services.adapters.bigquery_feature_fetcher import BigQueryFeatureFetcher
from app.services.adapters.feature_online_store_fetcher import FeatureOnlineStoreFetcher

pytestmark = pytest.mark.live_gcp


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"live_gcp parity requires env {name}")
    return value


def _property_ids() -> list[str]:
    raw = os.environ.get("LIVE_GCP_PROPERTY_IDS", "").strip()
    if not raw:
        pytest.skip("set LIVE_GCP_PROPERTY_IDS to a comma-separated property_id list")
    return [part.strip() for part in raw.split(",") if part.strip()]


def test_bigquery_and_fos_match_feature_values_live() -> None:
    project_id = _env("PROJECT_ID")
    location = _env("VERTEX_LOCATION")
    store_id = _env("VERTEX_FEATURE_ONLINE_STORE_ID")
    view_id = _env("VERTEX_FEATURE_VIEW_ID")
    endpoint = _env("VERTEX_FEATURE_ONLINE_STORE_ENDPOINT")
    features_table = _env("LIVE_GCP_FEATURES_TABLE")
    property_ids = _property_ids()

    bq_fetcher = BigQueryFeatureFetcher(
        features_table=features_table,
        client=bigquery.Client(project=project_id),
    )
    fos_fetcher = FeatureOnlineStoreFetcher(
        feature_view=(
            f"projects/{project_id}/locations/{location}/"
            f"featureOnlineStores/{store_id}/featureViews/{view_id}"
        ),
        endpoint_resolver=lambda: endpoint,
    )

    bq_rows = bq_fetcher.fetch(property_ids)
    fos_rows = fos_fetcher.fetch(property_ids)
    tolerance = float(os.environ.get("LIVE_GCP_FEATURE_TOLERANCE", "1e-6"))

    for property_id in property_ids:
        bq_row = bq_rows[property_id]
        fos_row = fos_rows[property_id]
        for attr in ("ctr", "fav_rate", "inquiry_rate"):
            left = getattr(bq_row, attr)
            right = getattr(fos_row, attr)
            if left is None or right is None:
                assert left is None and right is None, (
                    f"feature parity mismatch for {property_id}.{attr}: "
                    f"bq={left!r}, fos={right!r}"
                )
                continue
            assert abs(left - right) <= tolerance, (
                f"feature parity mismatch for {property_id}.{attr}: "
                f"bq={left}, fos={right}, tolerance={tolerance}"
            )
