from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import redis

from common.core.logging import get_logger

logger = get_logger(__name__)

_REDIS_HOST = os.getenv("REDIS_HOST", "redis")
_REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
_SEARCH_CACHE_TTL = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "120"))

# 接続失敗時もアプリを落とさないよう遅延初期化する
_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=_REDIS_HOST,
            port=_REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=1,
        )
    return _client


def _make_cache_key(params: dict[str, Any]) -> str:
    normalized = json.dumps(params, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"search_result:{digest}"


def get_cached_search(params: dict[str, Any]) -> dict | None:
    """キャッシュヒット時は dict を返す。ミスまたは Redis 障害時は None。"""
    try:
        raw = _get_client().get(_make_cache_key(params))
        if raw:
            logger.debug("Cache hit", extra={"cache_key": _make_cache_key(params)})
            return json.loads(raw)
        logger.debug("Cache miss", extra={"cache_key": _make_cache_key(params)})
    except redis.ConnectionError as exc:
        logger.warning(
            "Redis connection error on get",
            extra={
                "error": str(exc),
                "host": _REDIS_HOST,
                "port": _REDIS_PORT,
            },
        )
    except redis.TimeoutError as exc:
        logger.warning(
            "Redis timeout on get",
            extra={
                "error": str(exc),
                "host": _REDIS_HOST,
                "port": _REDIS_PORT,
            },
        )
    except json.JSONDecodeError as exc:
        logger.error(
            "Failed to decode cached value",
            extra={
                "error": str(exc),
                "cache_key": _make_cache_key(params),
            },
        )
    except Exception as exc:
        logger.error(
            "Unexpected error on cache get",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
    return None


def set_cached_search(params: dict[str, Any], result: dict) -> None:
    """検索結果を TTL 付きでキャッシュする。Redis 障害時は無視。"""
    try:
        _get_client().setex(
            _make_cache_key(params),
            _SEARCH_CACHE_TTL,
            json.dumps(result, ensure_ascii=False),
        )
        logger.debug(
            "Cache set",
            extra={
                "cache_key": _make_cache_key(params),
                "ttl_seconds": _SEARCH_CACHE_TTL,
            },
        )
    except redis.ConnectionError as exc:
        logger.warning(
            "Redis connection error on set",
            extra={
                "error": str(exc),
                "host": _REDIS_HOST,
                "port": _REDIS_PORT,
            },
        )
    except redis.TimeoutError as exc:
        logger.warning(
            "Redis timeout on set",
            extra={
                "error": str(exc),
                "host": _REDIS_HOST,
                "port": _REDIS_PORT,
            },
        )
    except Exception as exc:
        logger.error(
            "Unexpected error on cache set",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
