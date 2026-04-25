"""Unit tests for scripts._common.resolve_api_target.

Pins the resolution order documented in
``docs/02_移行ロードマップ切り替え基盤.md §解決順序``:

    1. ``API_URL`` wins (mode=explicit). Token only when API_REQUIRE_TOKEN=truthy.
    2. ``TARGET=local`` uses LOCAL_API_URL with no token (mode=local).
    3. ``TARGET=gcp`` (default) resolves cloud_run_url + identity_token (mode=gcp).

The basis is intentionally small: it must not auto-detect Gateway / Cloud Run
or fall back across modes. These tests guard that minimal contract.
"""

from __future__ import annotations

import pytest

from scripts import _common


@pytest.fixture(autouse=True)
def _clear_target_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("TARGET", "LOCAL_API_URL", "API_URL", "API_REQUIRE_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def test_explicit_api_url_wins_over_target_and_skips_token_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_URL", "https://search.example.com/")
    monkeypatch.setenv("TARGET", "gcp")
    monkeypatch.setattr(
        _common, "cloud_run_url", lambda: pytest.fail("must not call cloud_run_url")
    )
    monkeypatch.setattr(_common, "identity_token", lambda: pytest.fail("must not mint a token"))

    resolved = _common.resolve_api_target()

    assert resolved.mode == "explicit"
    assert resolved.url == "https://search.example.com"
    assert resolved.token is None


@pytest.mark.parametrize("flag", ["1", "true", "yes", "on", "TRUE", "On"])
def test_explicit_api_url_mints_token_when_require_token_truthy(
    monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    monkeypatch.setenv("API_URL", "https://search.example.com")
    monkeypatch.setenv("API_REQUIRE_TOKEN", flag)
    monkeypatch.setattr(_common, "identity_token", lambda: "token-xyz")

    resolved = _common.resolve_api_target()

    assert resolved.mode == "explicit"
    assert resolved.token == "token-xyz"


def test_target_local_uses_default_local_url_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARGET", "local")
    monkeypatch.setattr(_common, "identity_token", lambda: pytest.fail("local must not mint token"))

    resolved = _common.resolve_api_target()

    assert resolved.mode == "local"
    assert resolved.url == "http://127.0.0.1:8080"
    assert resolved.token is None


def test_target_local_honors_local_api_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET", "local")
    monkeypatch.setenv("LOCAL_API_URL", "http://127.0.0.1:18080/")

    resolved = _common.resolve_api_target()

    assert resolved.mode == "local"
    assert resolved.url == "http://127.0.0.1:18080"


def test_target_gcp_default_resolves_cloud_run_url_and_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_common, "cloud_run_url", lambda: "https://search-api-xyz.run.app")
    monkeypatch.setattr(_common, "identity_token", lambda: "id-token")

    resolved = _common.resolve_api_target()

    assert resolved.mode == "gcp"
    assert resolved.url == "https://search-api-xyz.run.app"
    assert resolved.token == "id-token"


def test_unknown_target_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET", "staging")

    with pytest.raises(ValueError, match="TARGET must be either 'local' or 'gcp'"):
        _common.resolve_api_target()
