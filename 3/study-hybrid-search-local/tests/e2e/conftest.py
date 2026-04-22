"""Playwright E2E 用のライブサーバ fixture.

Phase 3 は uv + docker compose 構成で、/search は Meilisearch / Redis / PostgreSQL
のバックエンドに依存するが、`/`, `/metrics`, `/data` は純粋な Jinja2 テンプレート
レンダリングなのでバックエンド無しでも smoke 可能。
"""

from __future__ import annotations

import socket
import threading
import time

import httpx
import pytest
import uvicorn


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _UvicornThread(threading.Thread):
    def __init__(self, app, host: str, port: int) -> None:
        super().__init__(daemon=True)
        config = uvicorn.Config(
            app, host=host, port=port, log_level="warning", lifespan="on"
        )
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()


@pytest.fixture(scope="session")
def live_server() -> str:
    """uvicorn をバックグラウンドスレッドで起動し、/health が 200 を返すまで待つ."""
    from app.main import app

    host, port = "127.0.0.1", _find_free_port()
    thread = _UvicornThread(app, host, port)
    thread.start()

    base_url = f"http://{host}:{port}"
    deadline = time.time() + 10.0
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        thread.server.should_exit = True
        raise RuntimeError("uvicorn did not become ready within 10s")

    yield base_url

    thread.server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, live_server):
    """pytest-playwright の page fixture が使う base_url を live_server に揃える."""
    return {**browser_context_args, "base_url": live_server}
