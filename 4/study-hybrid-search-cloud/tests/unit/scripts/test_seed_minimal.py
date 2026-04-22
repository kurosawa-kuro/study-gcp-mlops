from __future__ import annotations

import subprocess

from scripts.dev import seed_minimal


def test_sync_meili_index_uses_terraform_output_and_cli(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, capture: bool = False, check: bool = True, timeout=None):
        calls.append(cmd)
        if cmd[:3] == ["terraform", "-chdir=infra/terraform/environments/main", "output"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://meili.example\n")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(seed_minimal, "run", _fake_run)

    seed_minimal._sync_meili_index("mlops-dev-a")

    assert calls[0][:3] == ["terraform", "-chdir=infra/terraform/environments/main", "output"]
    assert calls[1][:5] == ["uv", "run", "python", "-m", "ml.data.loaders.meili_sync"]
    assert "--require-identity-token" not in calls[1]
