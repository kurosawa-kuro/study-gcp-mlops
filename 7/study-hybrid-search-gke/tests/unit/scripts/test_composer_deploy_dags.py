"""Pin scripts/deploy/composer_deploy_dags.py — DAG GCS upload helper (Phase 7 W2-4).

検証:
- `terraform output composer_dag_bucket` が空文字 → early-return (rc=0)
  (Stage 1 / Stage 2 の `enable_composer=false` default 時に deploy_all を
  壊さない設計)
- terraform output が GCS prefix を返す → `gsutil cp` で `pipeline/dags/*.py`
  を upload (各 DAG file が `gsutil` 引数に並ぶ)
- DAG file 列挙が `__pycache__/` を除外する
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.deploy import composer_deploy_dags


def _fake_run_factory(stdout: str, returncode: int = 0):
    def _fake_run(cmd, capture=False, check=False):
        proc = MagicMock()
        proc.stdout = stdout
        proc.returncode = returncode
        return proc

    return _fake_run


def test_main_early_returns_when_dag_bucket_empty(monkeypatch, capsys) -> None:
    """`composer_dag_bucket=""` (= enable_composer=false) のとき rc=0 で skip。"""
    monkeypatch.setattr(
        composer_deploy_dags,
        "run",
        _fake_run_factory(stdout=json.dumps({})),
    )
    rc = composer_deploy_dags.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "Composer environment not provisioned" in captured.out


def test_main_uploads_dags_when_bucket_set(monkeypatch, capsys) -> None:
    """`composer_dag_bucket=gs://...` が返ったとき `gsutil cp` を呼ぶ。"""
    calls: list[list[str]] = []

    def _fake_run(cmd, capture=False, check=False):
        calls.append(list(cmd))
        proc = MagicMock()
        proc.returncode = 0
        if cmd[0] == "terraform":
            proc.stdout = json.dumps(
                {"composer_dag_bucket": {"value": "gs://composer-bucket/dags"}}
            )
        else:
            proc.stdout = ""
        return proc

    monkeypatch.setattr(composer_deploy_dags, "run", _fake_run)
    rc = composer_deploy_dags.main()
    assert rc == 0

    upload_calls = [c for c in calls if c[0] == "gsutil"]
    assert len(upload_calls) == 1, f"expected 1 gsutil call, got {len(upload_calls)}"
    upload_cmd = upload_calls[0]
    assert upload_cmd[:3] == ["gsutil", "-m", "cp"]
    assert upload_cmd[-1] == "gs://composer-bucket/dags"
    # DAG files (relative names) appear in cmd
    joined = " ".join(upload_cmd)
    for required_dag in (
        "daily_feature_refresh.py",
        "retrain_orchestration.py",
        "monitoring_validation.py",
        "_common.py",
    ):
        assert required_dag in joined, f"missing DAG file in upload args: {required_dag}"

    captured = capsys.readouterr()
    assert "uploading" in captured.out
    assert "composer-deploy-dags complete" in captured.out


def test_main_raises_when_terraform_output_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        composer_deploy_dags,
        "run",
        _fake_run_factory(stdout="", returncode=1),
    )
    with pytest.raises(SystemExit, match="terraform output -json failed"):
        composer_deploy_dags.main()


def test_main_raises_on_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        composer_deploy_dags,
        "run",
        _fake_run_factory(stdout="not valid json"),
    )
    with pytest.raises(SystemExit, match="terraform output JSON decode failed"):
        composer_deploy_dags.main()


def test_dag_file_listing_excludes_pycache() -> None:
    files = composer_deploy_dags._list_dag_files()
    assert files, "no DAG files found"
    names = {p.name for p in files}
    assert "__init__.py" in names  # __init__ も upload する (パッケージ整合)
    assert all("__pycache__" not in str(p) for p in files)
    # All resolved paths exist
    for p in files:
        assert isinstance(p, Path)
        assert p.is_file()
