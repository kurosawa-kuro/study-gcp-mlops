from __future__ import annotations

import json

from scripts.local import search_check


def test_search_check_fails_on_empty_results(monkeypatch, capsys) -> None:
    monkeypatch.setattr(search_check, "cloud_run_url", lambda: "https://example")
    monkeypatch.setattr(search_check, "identity_token", lambda: "token")
    monkeypatch.setattr(
        search_check,
        "http_json",
        lambda *_a, **_kw: (200, json.dumps({"request_id": "r1", "results": [], "model_path": None})),
    )
    rc = search_check.main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "results is empty" in err


def test_search_check_allows_empty_when_opt_in(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ALLOW_EMPTY_RESULTS", "1")
    monkeypatch.setattr(search_check, "cloud_run_url", lambda: "https://example")
    monkeypatch.setattr(search_check, "identity_token", lambda: "token")
    monkeypatch.setattr(
        search_check,
        "http_json",
        lambda *_a, **_kw: (200, json.dumps({"request_id": "r1", "results": [], "model_path": None})),
    )
    rc = search_check.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert '"results": []' in out
