from __future__ import annotations

import subprocess

from ml.data.loaders import meili_sync


class _DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _DummyClient:
    def __init__(self, payloads: list[dict]):
        self._payloads = payloads
        self.calls: list[dict] = []

    def get(self, _url: str, *, params: dict, headers: dict) -> _DummyResponse:
        self.calls.append({"params": params, "headers": headers})
        payload = self._payloads.pop(0) if self._payloads else {"results": []}
        return _DummyResponse(payload)


def test_resolve_latest_task_uid_accepts_index_uid_fallback() -> None:
    client = _DummyClient(payloads=[{"results": []}, {"results": [{"uid": 42}]}])
    uid = meili_sync._resolve_latest_task_uid(
        client=client,
        base="https://meili.example",
        headers={},
        index="properties",
    )
    assert uid == 42
    assert client.calls[0]["params"] == {"indexUids": "properties", "limit": 1}
    assert client.calls[1]["params"] == {"indexUid": "properties", "limit": 1}


def test_resolve_latest_task_uid_with_retry_eventually_finds_uid(monkeypatch) -> None:
    client = _DummyClient(payloads=[{"results": []}, {"results": [{"uid": 99}]}])
    monkeypatch.setattr(meili_sync.time, "sleep", lambda _s: None)

    uid = meili_sync._resolve_latest_task_uid_with_retry(
        client=client,
        base="https://meili.example",
        headers={},
        index="properties",
        timeout_sec=1,
        poll_sec=0.01,
    )

    assert uid == 99


def test_resolve_identity_token_falls_back_when_impersonation_denied(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, check: bool, text: bool, stdout: int):
        calls.append(cmd)
        if "--impersonate-service-account=sa-api@mlops-dev-a.iam.gserviceaccount.com" in cmd:
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd)
        if any(part.startswith("--audiences=") for part in cmd):
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd)
        class _Proc:
            stdout = "token-from-fallback\n"

        return _Proc()

    monkeypatch.setattr(meili_sync.id_token, "fetch_id_token", lambda *_args, **_kwargs: (_ for _ in ()).throw(Exception("adc failed")))
    monkeypatch.setattr(meili_sync.subprocess, "run", _fake_run)

    token = meili_sync._resolve_identity_token(
        base_url="https://meili.example",
        impersonate_service_account="sa-api@mlops-dev-a.iam.gserviceaccount.com",
    )

    assert token == "token-from-fallback"
    assert len(calls) == 3
    assert any("--impersonate-service-account=sa-api@mlops-dev-a.iam.gserviceaccount.com" in c for c in calls[0])
    assert calls[2] == ["gcloud", "auth", "print-identity-token"]


def test_headers_use_serverless_authorization(monkeypatch) -> None:
    monkeypatch.setattr(meili_sync, "_resolve_identity_token", lambda **_kwargs: "id-token")

    headers = meili_sync._headers(
        base_url="https://meili.example",
        api_key="",
        require_identity_token=True,
        impersonate_service_account="",
    )

    assert headers["x-serverless-authorization"] == "Bearer id-token"
    assert "authorization" not in headers
