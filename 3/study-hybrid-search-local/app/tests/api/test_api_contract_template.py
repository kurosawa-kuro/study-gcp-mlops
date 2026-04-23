"""Cross-phase API contract template tests for /search /feedback /readyz."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.dependencies import (
    get_cache_port,
    get_embedding_port,
    get_property_search_port,
    get_ranking_compare_log_port,
    get_record_feedback_usecase,
    get_reranking_port,
    get_search_log_port,
)
from app.main import app
from common.ports.inbound.feedback_usecase import FeedbackCommand
from common.ports.inbound.search_usecase import SearchQuery


client = TestClient(app)


class _FakePropertySearchPort:
    def search_candidates(self, query: SearchQuery) -> list[dict[str, Any]]:
        return [
            {"id": 1, "title": "Property A", "price": 80_000, "me5_score": 0.9, "lgbm_score": 0.8},
            {"id": 2, "title": "Property B", "price": 70_000, "me5_score": 0.8, "lgbm_score": 0.7},
        ]


class _FakeEmbeddingPort:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]


class _FakeRerankingPort:
    def rerank(
        self, query: SearchQuery, candidates: list[dict[str, Any]], query_vector: list[float]
    ) -> list[dict[str, Any]]:
        return list(candidates)


class _FakeCacheMiss:
    def get(self, key: str) -> dict[str, Any] | None:
        return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        return None


class _FakeSearchLogPort:
    def create_search_log(self, query, result_ids, me5_scores=None) -> int:
        return 42


class _FakeRankingCompareLogPort:
    def create_compare_log(self, search_log_id, meili_result_ids, reranked_result_ids) -> int:
        return 7


class _FakeRecordFeedbackUseCase:
    def execute(self, command: FeedbackCommand) -> dict[str, object]:
        return {
            "status": "ok",
            "property_id": command.property_id,
            "action": command.action,
            "search_log_updated": True,
        }


def _override_search_deps() -> None:
    app.dependency_overrides[get_property_search_port] = lambda: _FakePropertySearchPort()
    app.dependency_overrides[get_embedding_port] = lambda: _FakeEmbeddingPort()
    app.dependency_overrides[get_reranking_port] = lambda: _FakeRerankingPort()
    app.dependency_overrides[get_cache_port] = lambda: _FakeCacheMiss()
    app.dependency_overrides[get_search_log_port] = lambda: _FakeSearchLogPort()
    app.dependency_overrides[get_ranking_compare_log_port] = lambda: _FakeRankingCompareLogPort()


def _override_feedback_usecase() -> None:
    app.dependency_overrides[get_record_feedback_usecase] = lambda: _FakeRecordFeedbackUseCase()


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


def _assert_search_shape(body: dict[str, Any]) -> None:
    # Phase3 legacy response keys: search_log_id / items.
    assert "search_log_id" in body
    items = body.get("items")
    assert isinstance(items, list)
    assert len(items) > 0


def _assert_trace_identifier(body: dict[str, Any]) -> None:
    # Phase3 keeps traceability via integer search_log_id.
    assert isinstance(body.get("search_log_id"), int)
    assert body["search_log_id"] > 0


def _assert_result_item_required_fields(body: dict[str, Any]) -> None:
    first = body["items"][0]
    for key in ("id", "title", "price"):
        assert key in first


def _assert_feedback_shape(body: dict[str, Any]) -> None:
    # Phase3 legacy response keys: status / action.
    assert body.get("status") == "ok"
    assert body.get("action") == "click"


def test_api_contract_readyz_returns_ok() -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_api_contract_search_success_shape() -> None:
    _override_search_deps()
    try:
        r = client.get("/search", params={"q": "マンション", "city": "札幌市"})
    finally:
        _clear_overrides()
    assert r.status_code == 200
    _assert_search_shape(r.json())


def test_api_contract_search_has_trace_identifier() -> None:
    _override_search_deps()
    try:
        r = client.get("/search", params={"q": "マンション"})
    finally:
        _clear_overrides()
    assert r.status_code == 200
    _assert_trace_identifier(r.json())


def test_api_contract_search_result_item_required_fields() -> None:
    _override_search_deps()
    try:
        r = client.get("/search", params={"q": "マンション"})
    finally:
        _clear_overrides()
    assert r.status_code == 200
    _assert_result_item_required_fields(r.json())


def test_api_contract_feedback_accepts_click() -> None:
    _override_feedback_usecase()
    try:
        r = client.post(
            "/feedback",
            json={
                "user_id": 1,
                "property_id": 5,
                "action": "click",
                "search_log_id": 42,
            },
        )
    finally:
        _clear_overrides()
    assert r.status_code == 200
    _assert_feedback_shape(r.json())


def test_api_contract_search_validation_error() -> None:
    _override_search_deps()
    try:
        r = client.get("/search", params={"q": "test", "limit": 0})
    finally:
        _clear_overrides()
    assert r.status_code == 422


def test_api_contract_feedback_rejects_unknown_action() -> None:
    _override_feedback_usecase()
    try:
        r = client.post(
            "/feedback",
            json={
                "user_id": 1,
                "property_id": 5,
                "action": "teleport",
                "search_log_id": 42,
            },
        )
    finally:
        _clear_overrides()
    assert r.status_code == 422


def test_api_contract_feedback_validation_error() -> None:
    # Missing required field `property_id`.
    r = client.post(
        "/feedback",
        json={
            "user_id": 1,
            "action": "click",
            "search_log_id": 42,
        },
    )
    assert r.status_code == 422


def test_api_contract_search_unavailable_behavior() -> None:
    class _TimeoutPropertySearchPort:
        def search_candidates(self, query: SearchQuery) -> list[dict[str, Any]]:
            raise TimeoutError("Request timed out")

    app.dependency_overrides[get_property_search_port] = lambda: _TimeoutPropertySearchPort()
    app.dependency_overrides[get_embedding_port] = lambda: _FakeEmbeddingPort()
    app.dependency_overrides[get_reranking_port] = lambda: _FakeRerankingPort()
    app.dependency_overrides[get_cache_port] = lambda: _FakeCacheMiss()
    app.dependency_overrides[get_search_log_port] = lambda: _FakeSearchLogPort()
    app.dependency_overrides[get_ranking_compare_log_port] = lambda: _FakeRankingCompareLogPort()
    try:
        r = client.get("/search", params={"q": "test"})
    finally:
        _clear_overrides()
    assert r.status_code == 504
