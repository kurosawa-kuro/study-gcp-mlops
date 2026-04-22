"""Structural sanity checks for the GitHub Actions workflows.

This is not a YAML schema validator — it only enforces the few invariants that
keep the deploy pipeline coherent with the repo layout:

* every workflow specifies a ``name``, path-triggered pushes, and an ``id-token: write``
  permission (required for WIF OIDC),
* ``deploy-embedding-job.yml`` uses ``JOB: embedding-job``, ``ml/data/**`` path
  filter, and ``sa-job-embed`` service account (5-SA separation per CLAUDE.md),
* ``deploy-training-job.yml`` / ``deploy-api.yml`` each keep their workspace
  path filter (``ml/training/**`` / ``app/**``) + broad ``common/**`` filter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

REQUIRED_WORKFLOWS = (
    "ci.yml",
    "deploy-api.yml",
    "deploy-training-job.yml",
    "deploy-dataform.yml",
    "deploy-embedding-job.yml",
    "terraform.yml",
)


@pytest.mark.parametrize("filename", REQUIRED_WORKFLOWS)
def test_workflow_file_exists(filename: str) -> None:
    assert (WORKFLOWS_DIR / filename).is_file(), (
        f"missing .github/workflows/{filename} — required by the CI/CD matrix"
    )


@pytest.mark.parametrize(
    "filename",
    ["deploy-api.yml", "deploy-training-job.yml", "deploy-embedding-job.yml", "terraform.yml"],
)
def test_deploy_workflows_request_oidc_token(filename: str) -> None:
    text = (WORKFLOWS_DIR / filename).read_text()
    assert "id-token: write" in text, (
        f"{filename} must request id-token:write permission for Workload Identity Federation"
    )


def test_embedding_workflow_points_at_embedding_job() -> None:
    text = (WORKFLOWS_DIR / "deploy-embedding-job.yml").read_text()
    assert "JOB: embedding-job" in text
    assert "- ml/data/**" in text, (
        "deploy-embedding-job.yml path filter must include ml/data/** so the "
        "workflow fires when the embedding entrypoint / runner / adapters change"
    )
    assert "common/src/common/embeddings/**" in text, (
        "path filter must include common/src/common/embeddings/** — the encoder "
        "is shared between the API and the embedding-job"
    )
    assert "sa-job-embed" in text, (
        "embedding-job runs under the dedicated sa-job-embed service account "
        "(roadmap §13 / CLAUDE.md non-negotiables — 5 SA 分離)."
    )


def test_training_workflow_filter() -> None:
    text = (WORKFLOWS_DIR / "deploy-training-job.yml").read_text()
    # ml-based layout — triggers on any ml/training/ or common/ change.
    assert "- ml/training/**" in text
    assert "- common/**" in text


def test_legacy_api_workflow_keeps_broad_filter() -> None:
    text = (WORKFLOWS_DIR / "deploy-api.yml").read_text()
    assert "- app/**" in text
    assert "- common/**" in text
