from __future__ import annotations

import json

from scripts.local import accuracy_report


def test_accuracy_report_local_success(monkeypatch, tmp_path, capsys) -> None:
    cases = {
        "cases": [
            {
                "name": "c1",
                "query": "新宿 1LDK",
                "filters": {"max_rent": 150000},
                "top_k": 5,
                "relevant_property_ids": ["1001"],
            }
        ]
    }
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("TARGET", "local")
    monkeypatch.setenv("LOCAL_API_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("EVAL_CASES_FILE", str(cases_path))
    monkeypatch.setenv("EVAL_K", "5")
    monkeypatch.setattr(
        accuracy_report,
        "http_json",
        lambda *_a, **_kw: (
            200,
            json.dumps(
                {
                    "request_id": "r1",
                    "results": [
                        {"property_id": "1001", "final_rank": 1},
                        {"property_id": "9999", "final_rank": 2},
                    ],
                }
            ),
        ),
    )

    rc = accuracy_report.main()
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["target"] == "local"
    assert out["summary"]["hit_rate_at_5"] == 1.0
    assert out["summary"]["mrr_at_5"] == 1.0


def test_accuracy_report_fails_on_http_error(monkeypatch, tmp_path, capsys) -> None:
    cases = {
        "cases": [
            {
                "query": "新宿 1LDK",
                "filters": {},
                "top_k": 5,
                "relevant_property_ids": ["1001"],
            }
        ]
    }
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("TARGET", "local")
    monkeypatch.setenv("EVAL_CASES_FILE", str(cases_path))
    monkeypatch.setattr(accuracy_report, "http_json", lambda *_a, **_kw: (503, "unavailable"))

    rc = accuracy_report.main()
    assert rc == 1
    assert "accuracy-report search failed" in capsys.readouterr().err


def test_accuracy_report_fails_on_zero_hit_rate_gate(monkeypatch, tmp_path, capsys) -> None:
    cases = {
        "cases": [
            {
                "query": "新宿 1LDK",
                "filters": {},
                "top_k": 5,
                "relevant_property_ids": ["1001"],
            }
        ]
    }
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("TARGET", "local")
    monkeypatch.setenv("EVAL_CASES_FILE", str(cases_path))
    monkeypatch.setenv("EVAL_K", "5")
    monkeypatch.setenv("MIN_HIT_RATE_AT_K", "0.5")
    monkeypatch.setattr(
        accuracy_report,
        "http_json",
        lambda *_a, **_kw: (200, json.dumps({"request_id": "r1", "results": [{"property_id": "9999"}]})),
    )

    rc = accuracy_report.main()
    assert rc == 1
    assert "accuracy-report gate failed" in capsys.readouterr().err
