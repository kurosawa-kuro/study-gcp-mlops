from __future__ import annotations

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
