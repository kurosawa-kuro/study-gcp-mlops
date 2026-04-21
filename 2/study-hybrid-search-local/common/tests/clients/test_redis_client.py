"""
正常系テスト: clients/redis_client.py のキャッシュロジック
Redis 接続は unittest.mock でモック。
"""
from unittest.mock import MagicMock, patch

import pytest

from common.clients.redis_client import _make_cache_key, get_cached_search, set_cached_search


# ---------------------------------------------------------------------------
# _make_cache_key — 同じ params → 同じキー、順序違いでも同じキー
# ---------------------------------------------------------------------------
def test_make_cache_key_deterministic():
    params = {"q": "マンション", "city": "札幌市", "limit": 20}
    assert _make_cache_key(params) == _make_cache_key(params)


def test_make_cache_key_order_independent():
    a = {"q": "test", "city": "東京", "limit": 20}
    b = {"limit": 20, "city": "東京", "q": "test"}
    assert _make_cache_key(a) == _make_cache_key(b)


def test_make_cache_key_different_params():
    a = {"q": "マンション", "limit": 20}
    b = {"q": "アパート", "limit": 20}
    assert _make_cache_key(a) != _make_cache_key(b)


# ---------------------------------------------------------------------------
# get_cached_search / set_cached_search — Redis をモック
# ---------------------------------------------------------------------------
_PARAMS = {"q": "マンション", "city": "札幌市", "limit": 20}
_RESULT = {"count": 1, "items": [{"id": 1, "title": "物件A"}]}


def test_get_cached_search_hit():
    import json
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(_RESULT, ensure_ascii=False)

    with patch("common.clients.redis_client._get_client", return_value=mock_redis):
        result = get_cached_search(_PARAMS)

    assert result == _RESULT


def test_get_cached_search_miss():
    mock_redis = MagicMock()
    mock_redis.get.return_value = None

    with patch("common.clients.redis_client._get_client", return_value=mock_redis):
        result = get_cached_search(_PARAMS)

    assert result is None


def test_get_cached_search_redis_error_returns_none():
    mock_redis = MagicMock()
    mock_redis.get.side_effect = Exception("connection refused")

    with patch("common.clients.redis_client._get_client", return_value=mock_redis):
        result = get_cached_search(_PARAMS)

    assert result is None


def test_set_cached_search_calls_setex():
    mock_redis = MagicMock()

    with patch("common.clients.redis_client._get_client", return_value=mock_redis):
        set_cached_search(_PARAMS, _RESULT)

    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    assert args[0].startswith("search_result:")  # key
    assert args[1] == 120                         # TTL デフォルト値


def test_set_cached_search_redis_error_ignored():
    mock_redis = MagicMock()
    mock_redis.setex.side_effect = Exception("connection refused")

    with patch("common.clients.redis_client._get_client", return_value=mock_redis):
        set_cached_search(_PARAMS, _RESULT)  # 例外が伝播しないことを確認
