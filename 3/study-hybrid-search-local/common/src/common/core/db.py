import atexit
import os
import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg_pool import ConnectionPool


_POOL: ConnectionPool | None = None
_POOL_LOCK = threading.Lock()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


def _build_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "estate")
    user = os.getenv("POSTGRES_USER", "admin")
    password = _require_env("POSTGRES_PASSWORD")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def _close_pool() -> None:
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None


def _get_pool() -> ConnectionPool:
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = ConnectionPool(
                    conninfo=_build_conninfo(),
                    min_size=int(os.getenv("POSTGRES_POOL_MIN_SIZE", "1")),
                    max_size=int(os.getenv("POSTGRES_POOL_MAX_SIZE", "10")),
                    timeout=float(os.getenv("POSTGRES_POOL_TIMEOUT", "10")),
                    kwargs={"autocommit": False},
                )
                atexit.register(_close_pool)
    return _POOL


@contextmanager
def get_db_connection() -> Iterator[psycopg.Connection]:
    with _get_pool().connection() as conn:
        yield conn
