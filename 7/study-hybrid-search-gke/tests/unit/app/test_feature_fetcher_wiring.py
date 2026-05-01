"""Composition-root wiring for ``FEATURE_FETCHER_BACKEND`` (Phase 7 PR-2).

PR-2 introduces ``SearchBuilder.resolve_feature_fetcher`` but does NOT
plug the result into ``Container``. PR-4 (KServe reranker → FOS opt-in)
is the consumer. These tests pin down:

- Default = ``bq`` (Strangler 原則: 既存挙動を変えない)
- ``online_store`` 選択 + 必要 settings 揃えば ``FeatureOnlineStoreFetcher``
- ``online_store`` 選択でも settings 不足なら WARN + ``None`` フォールバック
- ``InMemoryFeatureFetcher`` fake が Port を充足する (型契約の sanity)

Phase 7 ``docs/02_移行ロードマップ.md`` §3.2 受け入れ条件 (ローカル):
- composition root のレイヤ境界を `make check-layers` が PASS
- in-memory fake fetcher 経由で ranking が動作 (in_memory + Port の sanity)
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

from app.container.search import SearchBuilder
from app.services.adapters.bigquery_feature_fetcher import BigQueryFeatureFetcher
from app.services.adapters.feature_online_store_fetcher import FeatureOnlineStoreFetcher
from app.services.protocols.feature_fetcher import FeatureFetcher, FeatureRow
from app.settings import ApiSettings
from tests._fakes import InMemoryFeatureFetcher


class _FakeContext:
    def __init__(self, settings: ApiSettings, *, logger: logging.Logger | None = None) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger("test.feature_fetcher")

    def _bigquery(self) -> Any:
        return MagicMock()


def _settings(**overrides: object) -> ApiSettings:
    base: dict[str, object] = {
        "project_id": "mlops-test",
        "vertex_location": "asia-northeast1",
        "enable_search": True,
        "feature_fetcher_backend": "bq",
        "vertex_feature_online_store_id": "",
        "vertex_feature_view_id": "",
        "vertex_feature_online_store_endpoint": "",
        "meili_base_url": "",
        "kserve_encoder_url": "",
        "kserve_reranker_url": "",
        "ranking_log_topic": "",
        "feedback_topic": "",
        "retrain_topic": "",
    }
    base.update(overrides)
    return ApiSettings(**base)  # type: ignore[arg-type]


def _builder(settings: ApiSettings) -> SearchBuilder:
    return SearchBuilder(_FakeContext(settings))


# ----------------------------------------------------------------------------
# ApiSettings field defaults
# ----------------------------------------------------------------------------


def test_apisettings_feature_fetcher_backend_defaults_to_bq() -> None:
    settings = ApiSettings()
    assert settings.feature_fetcher_backend == "bq"
    assert settings.vertex_feature_online_store_id == ""
    assert settings.vertex_feature_view_id == ""
    assert settings.vertex_feature_online_store_endpoint == ""


# ----------------------------------------------------------------------------
# resolve_feature_fetcher routing
# ----------------------------------------------------------------------------


def test_resolve_returns_bq_fetcher_for_default_backend() -> None:
    builder = _builder(_settings(feature_fetcher_backend="bq"))
    fetcher = builder.resolve_feature_fetcher()
    assert isinstance(fetcher, BigQueryFeatureFetcher)


def test_resolve_returns_fos_fetcher_when_fully_configured() -> None:
    builder = _builder(
        _settings(
            feature_fetcher_backend="online_store",
            vertex_feature_online_store_id="property_features_store",
            vertex_feature_view_id="property_features_view",
            vertex_feature_online_store_endpoint="abc.asia-northeast1-fos.googleapis.com",
        )
    )

    fetcher = builder.resolve_feature_fetcher()

    assert isinstance(fetcher, FeatureOnlineStoreFetcher)
    assert fetcher._feature_view == (
        "projects/mlops-test/locations/asia-northeast1/featureOnlineStores/"
        "property_features_store/featureViews/property_features_view"
    )


def test_resolve_falls_back_to_none_when_online_store_id_missing(caplog) -> None:
    builder = _builder(
        _settings(
            feature_fetcher_backend="online_store",
            vertex_feature_online_store_id="",
            vertex_feature_view_id="property_features_view",
            vertex_feature_online_store_endpoint="abc.asia-northeast1-fos.googleapis.com",
        )
    )

    with caplog.at_level(logging.WARNING, logger="test.feature_fetcher"):
        result = builder.resolve_feature_fetcher()

    assert result is None
    assert any(
        "FEATURE_FETCHER_BACKEND=online_store" in record.message and "disabling" in record.message
        for record in caplog.records
    )


def test_resolve_falls_back_when_endpoint_missing() -> None:
    """Without the regional public endpoint, FOS data-plane cannot be reached."""
    builder = _builder(
        _settings(
            feature_fetcher_backend="online_store",
            vertex_feature_online_store_id="store",
            vertex_feature_view_id="view",
            vertex_feature_online_store_endpoint="",
        )
    )
    assert builder.resolve_feature_fetcher() is None


def test_resolve_falls_back_when_view_id_missing() -> None:
    builder = _builder(
        _settings(
            feature_fetcher_backend="online_store",
            vertex_feature_online_store_id="store",
            vertex_feature_view_id="",
            vertex_feature_online_store_endpoint="abc.example.com",
        )
    )
    assert builder.resolve_feature_fetcher() is None


# ----------------------------------------------------------------------------
# Fake satisfies the Port contract
# ----------------------------------------------------------------------------


def test_in_memory_feature_fetcher_satisfies_port() -> None:
    """``InMemoryFeatureFetcher`` is consumed via the ``FeatureFetcher`` Port."""
    rows = {"p001": FeatureRow(property_id="p001", ctr=0.1, fav_rate=0.2, inquiry_rate=0.3)}
    fake: FeatureFetcher = InMemoryFeatureFetcher(rows=rows)

    out = fake.fetch(["p001", "p002"])

    assert out["p001"] == FeatureRow(property_id="p001", ctr=0.1, fav_rate=0.2, inquiry_rate=0.3)
    assert out["p002"] == FeatureRow(property_id="p002", ctr=None, fav_rate=None, inquiry_rate=None)
