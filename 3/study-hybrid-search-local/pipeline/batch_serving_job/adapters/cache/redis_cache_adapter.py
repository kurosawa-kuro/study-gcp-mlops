from __future__ import annotations

import json
from typing import Any

import redis

from common.core.logging import get_logger

logger = get_logger(__name__)


class RedisCacheAdapter:
    def __init__(self, client: redis.Redis, default_ttl_seconds: int = 120) -> None:
        self._client = client
        self._default_ttl = default_ttl_seconds

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self._client.get(key)
            if raw:
                return json.loads(raw)
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            logger.warning("redis_cache_get_error", extra={"error": str(exc)})
        except json.JSONDecodeError as exc:
            logger.error("redis_cache_decode_error", extra={"key": key, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.error("redis_cache_unexpected_error", extra={"error": str(exc), "error_type": type(exc).__name__})
        return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False))
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            logger.warning("redis_cache_set_error", extra={"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.error("redis_cache_unexpected_error", extra={"error": str(exc), "error_type": type(exc).__name__})
