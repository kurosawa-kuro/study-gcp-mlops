"""
正常系テスト: API エンドポイント（/health, /search, /feedback）
外部依存（DB / Meilisearch / Redis）は dependency_overrides で差し替え。
"""
from typing import Any

from fastapi.testclient import TestClient

from app.dependencies import (
    get_cache_port,
    get_embedding_port,
    get_record_feedback_usecase,
    get_property_search_port,
    get_ranking_compare_log_port,
    get_reranking_port,
    get_search_log_port,
)
from app.main import app
from common.ports.inbound.feedback_usecase import FeedbackCommand
from common.ports.inbound.search_usecase import SearchQuery

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fake ports
# ---------------------------------------------------------------------------
_FAKE_ITEMS = [
    {"id": 1, "title": "物件A", "price": 80000, "me5_score": 0.9, "lgbm_score": 0.8},
    {"id": 2, "title": "物件B", "price": 70000, "me5_score": 0.7, "lgbm_score": 0.6},
]


class _FakePropertySearchPort:
    def search_candidates(self, query: SearchQuery) -> list[dict[str, Any]]:
        return list(_FAKE_ITEMS)


class _FakeEmbeddingPort:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]


class _FakeRerankingPort:
    def rerank(self, query: SearchQuery, candidates, query_vector) -> list[dict[str, Any]]:
        return list(candidates)


class _FakeCacheMiss:
    def get(self, key: str) -> dict[str, Any] | None:
        return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        pass


class _FakeCacheHit:
    _response = {
        "search_log_id": 99,
        "compare_log_id": 5,
        "count": 1,
        "items": [{"id": 10, "title": "キャッシュ物件"}],
    }

    def get(self, key: str) -> dict[str, Any] | None:
        return self._response

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        pass


class _FakeSearchLogPort:
    def create_search_log(self, query, result_ids, me5_scores=None) -> int:
        return 42


class _FakeRankingCompareLogPort:
    def create_compare_log(self, search_log_id, meili_result_ids, reranked_result_ids) -> int:
        return 7


class _FakeRecordFeedbackUseCase:
    def __init__(self, updated=True, raise_error: Exception | None = None) -> None:
        self._updated = updated
        self._raise_error = raise_error

    def execute(self, command: FeedbackCommand) -> dict[str, object]:
        if self._raise_error is not None:
            raise self._raise_error
        return {
            "status": "ok",
            "property_id": command.property_id,
            "action": command.action,
            "search_log_updated": self._updated,
        }


def _override_search_deps(cache_port=None):
    """依存関係をまとめて差し替えるヘルパー。"""
    app.dependency_overrides[get_property_search_port] = lambda: _FakePropertySearchPort()
    app.dependency_overrides[get_embedding_port] = lambda: _FakeEmbeddingPort()
    app.dependency_overrides[get_reranking_port] = lambda: _FakeRerankingPort()
    app.dependency_overrides[get_cache_port] = lambda: (cache_port or _FakeCacheMiss())
    app.dependency_overrides[get_search_log_port] = lambda: _FakeSearchLogPort()
    app.dependency_overrides[get_ranking_compare_log_port] = lambda: _FakeRankingCompareLogPort()


def _clear_overrides():
    app.dependency_overrides.clear()


def _override_feedback_usecase(usecase: _FakeRecordFeedbackUseCase):
    app.dependency_overrides[get_record_feedback_usecase] = lambda: usecase


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /search  — cache miss
# ---------------------------------------------------------------------------
def test_search_happy_path():
    _override_search_deps()
    try:
        resp = client.get("/search", params={"q": "マンション", "city": "札幌市"})
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    body = resp.json()
    assert body["search_log_id"] == 42
    assert body["compare_log_id"] == 7
    assert body["count"] == 2
    assert body["items"][0]["id"] == 1


def test_search_cache_hit():
    _override_search_deps(cache_port=_FakeCacheHit())
    try:
        resp = client.get("/search", params={"q": "マンション"})
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    assert resp.json()["search_log_id"] == 99


# ---------------------------------------------------------------------------
# /feedback
# ---------------------------------------------------------------------------
def test_feedback_happy_path():
    _override_feedback_usecase(_FakeRecordFeedbackUseCase(updated=True))
    try:
        resp = client.post(
            "/feedback",
            json={
                "user_id": 1,
                "property_id": 5,
                "action": "favorite",
                "search_log_id": 42,
            },
        )
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["property_id"] == 5
    assert body["action"] == "favorite"
    assert body["search_log_updated"] is True

# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------
def test_search_empty_query():
    """Test search with empty query string."""
    _override_search_deps()
    try:
        resp = client.get("/search", params={"q": ""})
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_search_query_too_long():
    """Test search with query exceeding max_length (500)."""
    long_query = "a" * 501
    resp = client.get("/search", params={"q": long_query})
    
    # Should fail validation with 422
    assert resp.status_code == 422


def test_search_invalid_limit():
    """Test search with invalid limit (should fail validation)."""
    resp = client.get("/search", params={"q": "test", "limit": 0})
    assert resp.status_code == 422

    resp = client.get("/search", params={"q": "test", "limit": 101})
    assert resp.status_code == 422



def test_search_invalid_candidate_limit():
    """Test search with invalid candidate_limit (should fail validation)."""
    resp = client.get("/search", params={"q": "test", "candidate_limit": 0})
    assert resp.status_code == 422

    resp = client.get("/search", params={"q": "test", "candidate_limit": 201})
    assert resp.status_code == 422


def test_search_meilisearch_unavailable():
    """Test search when Meilisearch is unavailable (ConnectionError)."""

    class _ErrorPropertySearchPort:
        def search_candidates(self, query: SearchQuery) -> list[dict[str, Any]]:
            raise ConnectionError("Connection refused")

    app.dependency_overrides[get_property_search_port] = lambda: _ErrorPropertySearchPort()
    app.dependency_overrides[get_embedding_port] = lambda: _FakeEmbeddingPort()
    app.dependency_overrides[get_reranking_port] = lambda: _FakeRerankingPort()
    app.dependency_overrides[get_cache_port] = lambda: _FakeCacheMiss()
    app.dependency_overrides[get_search_log_port] = lambda: _FakeSearchLogPort()
    app.dependency_overrides[get_ranking_compare_log_port] = lambda: _FakeRankingCompareLogPort()
    try:
        resp = client.get("/search", params={"q": "test"})
    finally:
        _clear_overrides()

    # Global exception handler should return 500 for generic ConnectionError
    assert resp.status_code == 500


def test_search_timeout():
    """Test search when request times out."""

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
        resp = client.get("/search", params={"q": "test"})
    finally:
        _clear_overrides()

    assert resp.status_code == 504


def test_feedback_invalid_action():
    """Test feedback with invalid action (should fail validation)."""
    resp = client.post(
        "/feedback",
        json={
            "user_id": 1,
            "property_id": 5,
            "action": "invalid_action",
            "search_log_id": 42,
        },
    )
    
    # Should fail validation with 422
    assert resp.status_code == 422


def test_feedback_invalid_property_id():
    """Test feedback with invalid property_id (should fail validation)."""
    resp = client.post(
        "/feedback",
        json={
            "user_id": 1,
            "property_id": 0,  # property_id must be > 0
            "action": "favorite",
            "search_log_id": 42,
        },
    )
    
    # Should fail validation with 422
    assert resp.status_code == 422


def test_feedback_invalid_search_log_id():
    """Test feedback with invalid search_log_id (should fail validation)."""
    resp = client.post(
        "/feedback",
        json={
            "user_id": 1,
            "property_id": 5,
            "action": "favorite",
            "search_log_id": 0,  # search_log_id must be > 0 or None
        },
    )
    
    # Should fail validation with 422
    assert resp.status_code == 422


def test_feedback_not_found():
    """Test feedback when search_log_id is not found in database."""
    _override_feedback_usecase(_FakeRecordFeedbackUseCase(raise_error=LookupError("search_log_id not found")))
    try:
        resp = client.post(
            "/feedback",
            json={
                "user_id": 1,
                "property_id": 5,
                "action": "favorite",
                "search_log_id": 99999,  # Non-existent ID
            },
        )
    finally:
        _clear_overrides()

    # apply_feedback returns None for not found, API returns 404
    assert resp.status_code == 404


def test_feedback_server_error():
    """Test feedback when database error occurs."""
    _override_feedback_usecase(_FakeRecordFeedbackUseCase(raise_error=Exception("Database connection failed")))
    try:
        resp = client.post(
            "/feedback",
            json={
                "user_id": 1,
                "property_id": 5,
                "action": "favorite",
                "search_log_id": 42,
            },
        )
    finally:
        _clear_overrides()

    assert resp.status_code == 500
