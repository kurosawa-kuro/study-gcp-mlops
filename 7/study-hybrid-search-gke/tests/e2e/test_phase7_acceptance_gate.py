"""Opt-in live acceptance gate for the Phase 7 end goal.

This test is intentionally skipped unless the operator explicitly opts in.
Its purpose is not local CI coverage; it is to encode the *true* acceptance
contract for this phase in executable form:

- clean destroy
- one-shot deploy-all
- search components all non-zero
- live ConfigMap points at canonical Vertex backends
- VVS smoke
- FOS feature fetch
- feedback / ranking smoke
- accuracy gate

Run manually only on the dedicated dev project:

    RUN_LIVE_GCP_ACCEPTANCE=1 pytest tests/e2e/test_phase7_acceptance_gate.py -m live_gcp
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.live_gcp

REPO_ROOT = Path(__file__).resolve().parents[2]


def _require_live_acceptance() -> None:
    if os.environ.get("RUN_LIVE_GCP_ACCEPTANCE", "").strip() != "1":
        pytest.skip("set RUN_LIVE_GCP_ACCEPTANCE=1 to run destructive Phase 7 acceptance gate")


def _run(cmd: list[str], *, timeout: int) -> None:
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + "\n" + proc.stderr).splitlines()[-40:])
        raise AssertionError(f"command failed rc={proc.returncode}: {' '.join(cmd)}\n{tail}")


def _run_capture(cmd: list[str], *, timeout: int) -> str:
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + "\n" + proc.stderr).splitlines()[-40:])
        raise AssertionError(f"command failed rc={proc.returncode}: {' '.join(cmd)}\n{tail}")
    return proc.stdout


def test_phase7_pdca_acceptance_gate_live() -> None:
    _require_live_acceptance()

    _run(["make", "destroy-all"], timeout=1800)
    _run(["make", "deploy-all"], timeout=3600)
    configmap_yaml = _run_capture(
        ["kubectl", "get", "configmap", "-n", "search", "search-api-config", "-o", "yaml"],
        timeout=120,
    )
    assert "semantic_backend: vertex_vector_search" in configmap_yaml
    assert "feature_fetcher_backend: online_store" in configmap_yaml
    _run(["make", "ops-search-components"], timeout=300)
    _run(["uv", "run", "python", "-m", "scripts.ops.vertex.vector_search"], timeout=300)
    _run(["make", "ops-vertex-feature-group"], timeout=300)
    _run(["make", "ops-feedback"], timeout=300)
    _run(["make", "ops-ranking"], timeout=300)
    _run(["make", "ops-accuracy-report"], timeout=300)
