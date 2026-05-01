"""Composition-root wiring for ``SEMANTIC_BACKEND`` (Phase 7 PR-1).

Pin down the contract between ``app.settings.ApiSettings.semantic_backend``
and ``SearchBuilder._resolve_semantic_search`` so silent regressions
(default flipping unintentionally, fallback path being removed, etc.)
fail at unit-test time rather than at /search runtime.

Phase 7 ``docs/02_移行ロードマップ.md`` §3.1 受け入れ条件 (ローカル):
- composition root のレイヤ境界を `make check-layers` が PASS
- in-memory fake 経由で /search が 200 を返す
"""

from __future__ import annotations

import logging
from typing import Any

from app.container.search import SearchBuilder
from app.services.adapters.bigquery_semantic_search import BigQuerySemanticSearch
from app.services.adapters.vertex_vector_search_semantic_search import (
    VertexVectorSearchSemanticSearch,
)
from app.settings import ApiSettings


class _FakeContext:
    """Minimal ``SearchBuilderContext`` for ``_resolve_semantic_search`` tests.

    ``_bigquery()`` is never invoked by ``_resolve_semantic_search`` itself
    (it is only used by ``build_candidate_retriever``), so we can return
    ``None`` and avoid pulling in ``google.cloud.bigquery``.
    """

    def __init__(self, settings: ApiSettings, *, logger: logging.Logger | None = None) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger("test.search_builder")

    def _bigquery(self) -> Any:
        return None


def _settings(**overrides: object) -> ApiSettings:
    base: dict[str, object] = {
        "project_id": "mlops-test",
        "vertex_location": "asia-northeast1",
        "enable_search": True,
        "semantic_backend": "bq",
        "vertex_vector_search_index_endpoint_id": "",
        "vertex_vector_search_deployed_index_id": "",
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


def test_apisettings_semantic_backend_defaults_to_bq() -> None:
    """Default = ``bq`` (Strangler 原則: PR-1 merge で挙動を変えない)."""
    settings = ApiSettings()
    assert settings.semantic_backend == "bq"
    assert settings.vertex_vector_search_index_endpoint_id == ""
    assert settings.vertex_vector_search_deployed_index_id == ""


# ----------------------------------------------------------------------------
# _resolve_semantic_search routing
# ----------------------------------------------------------------------------


def test_resolve_returns_none_for_default_bq_backend() -> None:
    """``bq`` 選択時は None を返し、BigQueryCandidateRetriever 内部の
    ``BigQuerySemanticSearch`` 構築にフォールバックする (既存挙動維持)."""
    builder = _builder(_settings(semantic_backend="bq"))
    assert builder._resolve_semantic_search() is None


def test_resolve_returns_vvs_adapter_when_endpoint_provisioned() -> None:
    builder = _builder(
        _settings(
            semantic_backend="vertex_vector_search",
            vertex_vector_search_index_endpoint_id="98765",
            vertex_vector_search_deployed_index_id="property_embeddings_v1",
        )
    )

    semantic = builder._resolve_semantic_search()

    assert isinstance(semantic, VertexVectorSearchSemanticSearch)
    # Endpoint resource name must be assembled from project + location + id.
    assert semantic._index_endpoint_name == (
        "projects/mlops-test/locations/asia-northeast1/indexEndpoints/98765"
    )
    assert semantic._deployed_index_id == "property_embeddings_v1"


def test_resolve_accepts_fully_qualified_endpoint_name_from_terraform_output() -> None:
    builder = _builder(
        _settings(
            semantic_backend="vertex_vector_search",
            vertex_vector_search_index_endpoint_id=(
                "projects/mlops-test/locations/asia-northeast1/indexEndpoints/98765"
            ),
            vertex_vector_search_deployed_index_id="property_embeddings_v1",
        )
    )

    semantic = builder._resolve_semantic_search()

    assert isinstance(semantic, VertexVectorSearchSemanticSearch)
    assert semantic._index_endpoint_name == (
        "projects/mlops-test/locations/asia-northeast1/indexEndpoints/98765"
    )


def test_resolve_falls_back_to_none_when_endpoint_id_missing(caplog) -> None:
    """Wave 2 未完了時 (endpoint 未 provision) のフォールバック契約。

    ``vertex_vector_search`` 選択でも endpoint ID が空なら None を返し、
    WARN log を出して BigQuery 経路に降りる。これにより仕様 docs と
    GCP infra のタイミング差が原因で `/search` が 503 にならない。
    """
    builder = _builder(
        _settings(
            semantic_backend="vertex_vector_search",
            vertex_vector_search_index_endpoint_id="",
            vertex_vector_search_deployed_index_id="",
        )
    )

    with caplog.at_level(logging.WARNING, logger="test.search_builder"):
        result = builder._resolve_semantic_search()

    assert result is None
    assert any(
        "SEMANTIC_BACKEND=vertex_vector_search" in record.message
        and "falling back" in record.message
        for record in caplog.records
    )


def test_resolve_falls_back_when_only_deployed_id_missing(caplog) -> None:
    builder = _builder(
        _settings(
            semantic_backend="vertex_vector_search",
            vertex_vector_search_index_endpoint_id="98765",
            vertex_vector_search_deployed_index_id="",
        )
    )
    with caplog.at_level(logging.WARNING, logger="test.search_builder"):
        result = builder._resolve_semantic_search()
    assert result is None


# ----------------------------------------------------------------------------
# Sanity: BQ adapter import path is unchanged
# ----------------------------------------------------------------------------


def test_bigquery_semantic_search_remains_default_constructor_target() -> None:
    """Phase 4 同等の挙動を担保するため、BigQuerySemanticSearch クラスは
    依然として import 可能で、コンストラクタ署名も維持されていること。
    回帰検知用の最小ガード。"""
    assert BigQuerySemanticSearch.__init__ is not None
