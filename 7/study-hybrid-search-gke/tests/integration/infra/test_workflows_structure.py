"""Verify GitHub Actions workflows have expected file-path filters and shape.

Phase 6 changes: search-api is deployed to GKE (not Cloud Run), Vertex Model
Monitoring v2 is scoped out. Workflows are updated accordingly.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"


def test_encoder_image_workflow_paths() -> None:
    text = (WORKFLOWS_DIR / "deploy-encoder-image.yml").read_text()
    assert "infra/run/services/encoder/Dockerfile" in text
    assert "ml/serving/**" in text


def test_reranker_image_workflow_paths() -> None:
    text = (WORKFLOWS_DIR / "deploy-reranker-image.yml").read_text()
    assert "infra/run/services/reranker/Dockerfile" in text
    assert "ml/serving/**" in text


def test_trainer_image_workflow_paths() -> None:
    text = (WORKFLOWS_DIR / "deploy-trainer-image.yml").read_text()
    assert "infra/run/jobs/training/Dockerfile" in text
    assert "ml/training/**" in text


def test_pipeline_workflow_paths() -> None:
    text = (WORKFLOWS_DIR / "deploy-pipeline.yml").read_text()
    assert "pipeline/data_job/**" in text
    assert "pipeline/training_job/**" in text
    assert "pipeline/workflow/**" in text
    assert "create_schedule" in text


def test_api_workflow_uses_gke_rollout() -> None:
    text = (WORKFLOWS_DIR / "deploy-api.yml").read_text()
    assert "- app/**" in text
    assert "- ml/**" in text
    # Phase 6: GKE 版。Cloud Run や Vertex Endpoint の env は持ち込まない
    assert "gcloud run deploy" not in text
    assert "VERTEX_ENCODER_ENDPOINT_ID" not in text
    assert "VERTEX_RERANKER_ENDPOINT_ID" not in text
    assert "kubectl" in text
    assert "rollout" in text
    assert "GKE_CLUSTER_NAME" in text
