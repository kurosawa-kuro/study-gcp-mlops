"""
SearchPropertiesUseCase の単体テスト。
外部接続なしで Fake Port を注入して検証する。
"""
from __future__ import annotations

from typing import Any


from common.ports.inbound.search_usecase import SearchQuery
from pipeline.application.search_properties import SearchPropertiesUseCase


# ---------------------------------------------------------------------------
# Fake Ports
# ---------------------------------------------------------------------------
class FakePropertySearchPort:
    def __init__(self, candidates: list[dict[str, Any]] | None = None) -> None:
        self._candidates = candidates if candidates is not None else [
            {"id": 1, "title": "物件A", "price": 80000},
            {"id": 2, "title": "物件B", "price": 70000},
        ]

    def search_candidates(self, query: SearchQuery) -> list[dict[str, Any]]:
        return list(self._candidates)


class FakeEmbeddingPort:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeRerankingPort:
    """候補を逆順にして me5_score を付与する。"""

    def rerank(
        self,
        query: SearchQuery,
        candidates: list[dict[str, Any]],
        query_vector: list[float] | None,
    ) -> list[dict[str, Any]]:
        result = list(reversed(candidates))
        for item in result:
            item["me5_score"] = 0.5
        return result


class FakeCacheMiss:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self.store[key] = value


class FakeCacheHit:
    _stored = {
        "search_log_id": 99,
        "compare_log_id": 5,
        "count": 1,
        "items": [{"id": 10}],
    }

    def get(self, key: str) -> dict[str, Any] | None:
        return self._stored

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        pass


class FakeSearchLogPort:
    def __init__(self, return_id: int = 42) -> None:
        self._id = return_id
        self.captured: dict | None = None

    def create_search_log(
        self,
        query: SearchQuery,
        result_ids: list[int],
        me5_scores: dict[int, float] | None = None,
    ) -> int:
        self.captured = {
            "query": query,
            "result_ids": result_ids,
            "me5_scores": me5_scores,
        }
        return self._id


class FakeRankingCompareLogPort:
    def __init__(self, return_id: int = 7) -> None:
        self._id = return_id
        self.captured: dict | None = None

    def create_compare_log(
        self,
        search_log_id: int,
        meili_result_ids: list[int],
        reranked_result_ids: list[int],
    ) -> int:
        self.captured = {
            "search_log_id": search_log_id,
            "meili_result_ids": meili_result_ids,
            "reranked_result_ids": reranked_result_ids,
        }
        return self._id


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------
def _make_usecase(
    candidates=None,
    cache_port=None,
    search_log_port=None,
    ranking_compare_log_port=None,
) -> tuple[SearchPropertiesUseCase, FakeSearchLogPort, FakeRankingCompareLogPort]:
    log_port = search_log_port or FakeSearchLogPort()
    compare_port = ranking_compare_log_port or FakeRankingCompareLogPort()
    usecase = SearchPropertiesUseCase(
        property_search_port=FakePropertySearchPort(candidates),
        embedding_port=FakeEmbeddingPort(),
        reranking_port=FakeRerankingPort(),
        cache_port=cache_port or FakeCacheMiss(),
        search_log_port=log_port,
        ranking_compare_log_port=compare_port,
        cache_ttl_seconds=60,
    )
    return usecase, log_port, compare_port


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_execute_returns_correct_structure():
    usecase, _, _ = _make_usecase()
    query = SearchQuery(q="マンション", city="札幌市")
    result = usecase.execute(query)

    assert result["search_log_id"] == 42
    assert result["compare_log_id"] == 7
    assert result["count"] == 2
    assert len(result["items"]) == 2


def test_execute_reranked_order():
    """FakeRerankingPort は候補を逆順にする → id=2 が先頭になる。"""
    usecase, _, _ = _make_usecase()
    query = SearchQuery(q="テスト")
    result = usecase.execute(query)

    assert result["items"][0]["id"] == 2
    assert result["items"][1]["id"] == 1


def test_execute_cache_hit_skips_search():
    """キャッシュヒット時はログ保存もランキングも呼ばれない。"""
    log_port = FakeSearchLogPort()
    compare_port = FakeRankingCompareLogPort()
    cache = FakeCacheHit()
    usecase = SearchPropertiesUseCase(
        property_search_port=FakePropertySearchPort(),
        embedding_port=FakeEmbeddingPort(),
        reranking_port=FakeRerankingPort(),
        cache_port=cache,
        search_log_port=log_port,
        ranking_compare_log_port=compare_port,
        cache_ttl_seconds=60,
    )
    result = usecase.execute(SearchQuery(q="マンション"))

    assert result["search_log_id"] == 99
    assert log_port.captured is None
    assert compare_port.captured is None


def test_execute_cache_miss_stores_result():
    """キャッシュミス後に結果がキャッシュに保存される。"""
    cache = FakeCacheMiss()
    usecase, _, _ = _make_usecase(cache_port=cache)
    query = SearchQuery(q="アパート")
    usecase.execute(query)

    assert len(cache.store) == 1
    stored = next(iter(cache.store.values()))
    assert "items" in stored
    assert stored["count"] == 2


def test_execute_passes_me5_scores_to_log():
    """me5_score が SearchLogPort に渡される。"""
    usecase, log_port, _ = _make_usecase()
    usecase.execute(SearchQuery(q="検索"))

    assert log_port.captured is not None
    me5 = log_port.captured["me5_scores"]
    assert me5 is not None
    assert all(v == 0.5 for v in me5.values())


def test_execute_passes_meili_ids_to_compare_log():
    """meili_result_ids（再ランク前）と reranked_result_ids（再ランク後）が別々に渡される。"""
    usecase, _, compare_port = _make_usecase()
    usecase.execute(SearchQuery(q="検索"))

    assert compare_port.captured is not None
    # FakeRerankingPort は逆順なので meili と reranked は異なる
    assert compare_port.captured["meili_result_ids"] == [1, 2]
    assert compare_port.captured["reranked_result_ids"] == [2, 1]


def test_execute_limit_applied():
    """limit=1 の場合、items は 1 件だけ返る。"""
    usecase, _, _ = _make_usecase()
    result = usecase.execute(SearchQuery(q="限定", limit=1))

    assert len(result["items"]) == 1
    assert result["count"] == 2  # count は再ランク後の全候補数


def test_execute_empty_candidates():
    """候補ゼロでも例外にならない。"""
    usecase, _, _ = _make_usecase(candidates=[])
    result = usecase.execute(SearchQuery(q="空"))

    assert result["count"] == 0
    assert result["items"] == []


def test_execute_no_query_skips_embedding():
    """q が空のとき、EmbeddingPort は呼ばれない（query_vector=None）。"""

    class _TrackingEmbedPort:
        called = False

        def embed_query(self, text: str) -> list[float]:
            self.called = True
            return [0.0]

    embed_port = _TrackingEmbedPort()
    usecase = SearchPropertiesUseCase(
        property_search_port=FakePropertySearchPort(),
        embedding_port=embed_port,
        reranking_port=FakeRerankingPort(),
        cache_port=FakeCacheMiss(),
        search_log_port=FakeSearchLogPort(),
        ranking_compare_log_port=FakeRankingCompareLogPort(),
    )
    usecase.execute(SearchQuery(q=""))

    assert not embed_port.called
