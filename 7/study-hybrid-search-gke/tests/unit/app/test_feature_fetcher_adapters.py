"""Unit tests for ``FeatureFetcher`` adapters (Phase 7 PR-2).

Both adapters are exercised without touching their underlying SDK:

- ``BigQueryFeatureFetcher``: ``bigquery.Client`` is replaced with a
  ``MagicMock`` whose ``.query().result()`` yields stub row dicts.
- ``FeatureOnlineStoreFetcher``: ``client_factory`` injection seam is
  used so ``google.cloud.aiplatform_v1beta1`` is never imported.

Phase 7 ``docs/tasks/TASKS_ROADMAP.md`` §3.2 受け入れ条件 (ローカル):
- mock で SDK call を stub した unit test PASS
- in-memory fake fetcher 経由で ranking が動作 (in_memory_feature_fetcher も別テストで使用)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.adapters.bigquery_feature_fetcher import BigQueryFeatureFetcher
from app.services.adapters.feature_online_store_fetcher import FeatureOnlineStoreFetcher
from app.services.protocols.feature_fetcher import FeatureRow

# ----------------------------------------------------------------------------
# BigQueryFeatureFetcher
# ----------------------------------------------------------------------------


def _bq_client_with_rows(rows: list[dict[str, Any]]) -> MagicMock:
    """Build a ``bigquery.Client`` mock whose ``.query().result()`` yields rows."""
    job = MagicMock()
    job.result.return_value = iter(rows)
    client = MagicMock()
    client.query.return_value = job
    return client


def test_bigquery_fetcher_returns_one_row_per_known_id() -> None:
    client = _bq_client_with_rows(
        [
            {"property_id": "p001", "ctr": 0.12, "fav_rate": 0.05, "inquiry_rate": 0.02},
            {"property_id": "p002", "ctr": 0.30, "fav_rate": 0.10, "inquiry_rate": 0.04},
        ]
    )
    fetcher = BigQueryFeatureFetcher(
        features_table="proj.feature_mart.property_features_daily",
        client=client,
    )

    out = fetcher.fetch(["p001", "p002"])

    assert out == {
        "p001": FeatureRow(property_id="p001", ctr=0.12, fav_rate=0.05, inquiry_rate=0.02),
        "p002": FeatureRow(property_id="p002", ctr=0.30, fav_rate=0.10, inquiry_rate=0.04),
    }


def test_bigquery_fetcher_returns_all_none_for_unknown_ids() -> None:
    """Missing properties get an explicit all-None row, not omitted."""
    client = _bq_client_with_rows(
        [{"property_id": "p001", "ctr": 0.12, "fav_rate": 0.05, "inquiry_rate": 0.02}]
    )
    fetcher = BigQueryFeatureFetcher(
        features_table="proj.feature_mart.property_features_daily",
        client=client,
    )

    out = fetcher.fetch(["p001", "p999"])

    assert out["p001"].ctr == pytest.approx(0.12)
    assert out["p999"] == FeatureRow(property_id="p999", ctr=None, fav_rate=None, inquiry_rate=None)


def test_bigquery_fetcher_skips_query_for_empty_input() -> None:
    """Optimisation: never round-trip BQ when there are no IDs."""
    client = _bq_client_with_rows([])
    fetcher = BigQueryFeatureFetcher(
        features_table="proj.feature_mart.property_features_daily",
        client=client,
    )

    assert fetcher.fetch([]) == {}
    client.query.assert_not_called()


def test_bigquery_fetcher_coerces_none_columns_to_none() -> None:
    """If the underlying row has NULLs, they pass through as ``None``."""
    client = _bq_client_with_rows(
        [{"property_id": "p001", "ctr": None, "fav_rate": 0.05, "inquiry_rate": None}]
    )
    fetcher = BigQueryFeatureFetcher(
        features_table="proj.feature_mart.property_features_daily",
        client=client,
    )
    out = fetcher.fetch(["p001"])
    assert out["p001"] == FeatureRow(property_id="p001", ctr=None, fav_rate=0.05, inquiry_rate=None)


def test_bigquery_fetcher_rejects_empty_features_table() -> None:
    with pytest.raises(ValueError, match="features_table"):
        BigQueryFeatureFetcher(features_table="", client=MagicMock())


# ----------------------------------------------------------------------------
# FeatureOnlineStoreFetcher
# ----------------------------------------------------------------------------


def _make_feature_value(double: float | None = None, int64: int | None = None) -> Any:
    val = MagicMock()
    val.double_value = double if double is not None else None
    val.float_value = None
    val.int64_value = int64 if int64 is not None else None
    return val


def _make_feature(name: str, value: Any) -> Any:
    fv = MagicMock()
    fv.name = name
    fv.value = value
    return fv


def _fos_client_returning(features_per_pid: dict[str, list[Any]]) -> Any:
    """Stub a FOS client; ``fetch_feature_values`` returns features per id."""
    client = MagicMock()

    def _fetch(*, request: Any) -> Any:
        # `request` is the duck-typed dict the adapter builds when no
        # SDK is present (see FeatureOnlineStoreFetcher._build_request).
        pid = request["data_key"]["key"]
        response = MagicMock()
        response.key_values.features = features_per_pid.get(pid, [])
        return response

    client.fetch_feature_values.side_effect = _fetch
    return client


def test_fos_fetcher_extracts_three_known_features() -> None:
    client = _fos_client_returning(
        {
            "p001": [
                _make_feature("ctr", _make_feature_value(double=0.12)),
                _make_feature("fav_rate", _make_feature_value(double=0.05)),
                _make_feature("inquiry_rate", _make_feature_value(double=0.02)),
            ]
        }
    )
    fetcher = FeatureOnlineStoreFetcher(
        feature_view="projects/x/locations/r/featureOnlineStores/s/featureViews/v",
        endpoint_resolver=lambda: "r-aiplatform.googleapis.com",
        client_factory=lambda _ep: client,
    )

    out = fetcher.fetch(["p001"])

    assert out["p001"] == FeatureRow(
        property_id="p001",
        ctr=pytest.approx(0.12),
        fav_rate=pytest.approx(0.05),
        inquiry_rate=pytest.approx(0.02),
    )


def test_fos_fetcher_ignores_unknown_feature_names() -> None:
    """Extra features in the FOS view (e.g. display fields) are dropped."""
    client = _fos_client_returning(
        {
            "p001": [
                _make_feature("ctr", _make_feature_value(double=0.12)),
                _make_feature("rent", _make_feature_value(int64=80_000)),
            ]
        }
    )
    fetcher = FeatureOnlineStoreFetcher(
        feature_view="projects/x/locations/r/featureOnlineStores/s/featureViews/v",
        endpoint_resolver=lambda: "r-aiplatform.googleapis.com",
        client_factory=lambda _ep: client,
    )

    out = fetcher.fetch(["p001"])

    assert out["p001"].ctr == pytest.approx(0.12)
    assert out["p001"].fav_rate is None
    assert out["p001"].inquiry_rate is None


def test_fos_fetcher_returns_all_none_when_per_id_call_raises() -> None:
    """A single failing fetch must not poison the whole batch."""
    client = MagicMock()

    def _fetch(*, request: Any) -> Any:
        pid = request["data_key"]["key"]
        if pid == "p_bad":
            raise RuntimeError("simulated FOS 503")
        response = MagicMock()
        response.key_values.features = [
            _make_feature("ctr", _make_feature_value(double=0.5)),
        ]
        return response

    client.fetch_feature_values.side_effect = _fetch
    fetcher = FeatureOnlineStoreFetcher(
        feature_view="projects/x/locations/r/featureOnlineStores/s/featureViews/v",
        endpoint_resolver=lambda: "r-aiplatform.googleapis.com",
        client_factory=lambda _ep: client,
    )

    out = fetcher.fetch(["p_good", "p_bad"])
    assert out["p_good"].ctr == pytest.approx(0.5)
    assert out["p_bad"] == FeatureRow(
        property_id="p_bad", ctr=None, fav_rate=None, inquiry_rate=None
    )


def test_fos_fetcher_returns_empty_for_empty_input() -> None:
    client = MagicMock()
    fetcher = FeatureOnlineStoreFetcher(
        feature_view="projects/x/locations/r/featureOnlineStores/s/featureViews/v",
        endpoint_resolver=lambda: "r-aiplatform.googleapis.com",
        client_factory=lambda _ep: client,
    )
    assert fetcher.fetch([]) == {}
    client.fetch_feature_values.assert_not_called()


def test_fos_fetcher_raises_when_endpoint_resolver_returns_empty() -> None:
    fetcher = FeatureOnlineStoreFetcher(
        feature_view="projects/x/locations/r/featureOnlineStores/s/featureViews/v",
        endpoint_resolver=lambda: "",
        client_factory=lambda _ep: MagicMock(),
    )
    with pytest.raises(RuntimeError, match="public endpoint is empty"):
        fetcher.fetch(["p001"])


def test_fos_fetcher_rejects_empty_feature_view() -> None:
    with pytest.raises(ValueError, match="feature_view"):
        FeatureOnlineStoreFetcher(
            feature_view="",
            endpoint_resolver=lambda: "endpoint",
        )
