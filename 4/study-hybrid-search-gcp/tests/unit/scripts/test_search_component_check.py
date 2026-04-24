from __future__ import annotations

import json

from scripts.local import search_component_check


def _mock_results() -> dict:
    return {
        "request_id": "r1",
        "model_path": "gs://models/run/model.txt",
        "results": [
            {
                "property_id": "p1",
                "final_rank": 1,
                "lexical_rank": 1,
                "semantic_rank": 2,
                "me5_score": 0.78,
                "score": 0.42,
            }
        ],
    }


def test_component_check_passes_when_all_components_contribute(monkeypatch) -> None:
    monkeypatch.setattr(search_component_check, "cloud_run_url", lambda: "https://example")
    monkeypatch.setattr(search_component_check, "identity_token", lambda: "token")
    def _http_json(method, url, **_kw):
        if method == "GET" and url.endswith("/readyz"):
            return 200, json.dumps({"status": "ready", "rerank_enabled": True})
        return 200, json.dumps(_mock_results())
    monkeypatch.setattr(
        search_component_check,
        "http_json",
        _http_json,
    )
    rc = search_component_check.main()
    assert rc == 0


def test_component_check_fails_when_meili_zero(monkeypatch, capsys) -> None:
    payload = _mock_results()
    payload["results"][0]["lexical_rank"] = 10000
    monkeypatch.setattr(search_component_check, "cloud_run_url", lambda: "https://example")
    monkeypatch.setattr(search_component_check, "identity_token", lambda: "token")
    def _http_json(method, url, **_kw):
        if method == "GET" and url.endswith("/readyz"):
            return 200, json.dumps({"status": "ready", "rerank_enabled": True})
        return 200, json.dumps(payload)
    monkeypatch.setattr(
        search_component_check,
        "http_json",
        _http_json,
    )
    rc = search_component_check.main()
    assert rc == 1
    assert "Meilisearch lexical contribution is zero" in capsys.readouterr().err


def test_component_check_fails_when_me5_zero(monkeypatch, capsys) -> None:
    payload = _mock_results()
    payload["results"][0]["semantic_rank"] = 10000
    payload["results"][0]["me5_score"] = 0.0
    monkeypatch.setattr(search_component_check, "cloud_run_url", lambda: "https://example")
    monkeypatch.setattr(search_component_check, "identity_token", lambda: "token")
    def _http_json(method, url, **_kw):
        if method == "GET" and url.endswith("/readyz"):
            return 200, json.dumps({"status": "ready", "rerank_enabled": True})
        return 200, json.dumps(payload)
    monkeypatch.setattr(
        search_component_check,
        "http_json",
        _http_json,
    )
    rc = search_component_check.main()
    assert rc == 1
    stderr = capsys.readouterr().err
    assert "ME5 semantic contribution is zero" in stderr
    assert "encoder is None -> query_vector=[]" in stderr


def test_component_check_fails_when_lightgbm_zero(monkeypatch, capsys) -> None:
    payload = _mock_results()
    payload["results"][0]["score"] = None
    monkeypatch.setattr(search_component_check, "cloud_run_url", lambda: "https://example")
    monkeypatch.setattr(search_component_check, "identity_token", lambda: "token")
    def _http_json(method, url, **_kw):
        if method == "GET" and url.endswith("/readyz"):
            return 200, json.dumps({"status": "ready", "rerank_enabled": False})
        return 200, json.dumps(payload)
    monkeypatch.setattr(
        search_component_check,
        "http_json",
        _http_json,
    )
    rc = search_component_check.main()
    assert rc == 1
    assert "LightGBM rerank contribution is zero" in capsys.readouterr().err


def test_component_check_local_target_uses_local_url_without_token(monkeypatch) -> None:
    monkeypatch.setenv("TARGET", "local")
    monkeypatch.setenv("LOCAL_API_URL", "http://127.0.0.1:8080")
    captured: list[tuple[str, str, str | None]] = []

    def _http_json(method, url, **kwargs):
        captured.append((method, url, kwargs.get("token")))
        if method == "GET" and url.endswith("/readyz"):
            return 200, json.dumps({"status": "ready", "rerank_enabled": True})
        return 200, json.dumps(_mock_results())

    monkeypatch.setattr(search_component_check, "cloud_run_url", lambda: "https://should-not-be-used")
    monkeypatch.setattr(search_component_check, "identity_token", lambda: "token")
    monkeypatch.setattr(search_component_check, "http_json", _http_json)

    rc = search_component_check.main()
    assert rc == 0
    assert captured[0][1].startswith("http://127.0.0.1:8080/")
    assert captured[0][2] is None

