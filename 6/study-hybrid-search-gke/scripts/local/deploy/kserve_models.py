"""Sync model artifacts from Vertex Model Registry into KServe InferenceService.

For each of the encoder and reranker, this script:
1. Resolves the latest production-alias Model version in Vertex Model Registry
2. Extracts the GCS artifact URI
3. Patches the corresponding `InferenceService` in namespace `kserve-inference`
   so that `spec.predictor.model.storageUri` (reranker) or
   `spec.predictor.containers[0].env[STORAGE_URI]` (encoder) points at the new URI

Phase 6 keeps the training pipeline unchanged — Vertex Model Registry remains
the canonical distribution point. Only the deployment target switches from
Vertex Endpoint to KServe InferenceService.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

from scripts._common import env, run

NAMESPACE = "kserve-inference"
ROLLOUT_TIMEOUT_SEC = 600


@dataclass
class ModelVersion:
    display_name: str
    version_id: str
    artifact_uri: str


def _require(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"[error] required env var {name} is empty")
    return value


def _resolve_latest(display_name: str, *, project_id: str, region: str) -> ModelVersion:
    """Resolve the 'production' alias (or most recent) version from Model Registry."""
    try:
        from google.cloud import aiplatform
    except ImportError:
        print(
            "[error] google-cloud-aiplatform not installed. run `make sync` first.",
            file=sys.stderr,
        )
        raise

    aiplatform.init(project=project_id, location=region)
    models = aiplatform.Model.list(filter=f'display_name="{display_name}"')
    if not models:
        raise RuntimeError(f"No model with display_name={display_name}")

    model = models[0]
    for candidate in models:
        aliases = getattr(candidate, "version_aliases", []) or []
        if "production" in aliases:
            model = candidate
            break

    artifact_uri = getattr(model, "uri", None) or getattr(model._gca_resource, "artifact_uri", "")
    if not artifact_uri:
        raise RuntimeError(f"Model {display_name} (version={model.version_id}) has no artifact_uri")
    return ModelVersion(
        display_name=display_name,
        version_id=str(model.version_id),
        artifact_uri=str(artifact_uri),
    )


def _patch_reranker_storage_uri(storage_uri: str) -> None:
    patch = {
        "spec": {
            "predictor": {
                "model": {
                    "storageUri": storage_uri,
                }
            }
        }
    }
    run(
        [
            "kubectl",
            "patch",
            "inferenceservice",
            "property-reranker",
            f"--namespace={NAMESPACE}",
            "--type=merge",
            f"--patch={json.dumps(patch)}",
        ]
    )


def _patch_encoder_storage_uri(storage_uri: str) -> None:
    """Encoder uses a custom Python predictor (Vertex CPR 規約を継承) —
    env var 名は ``AIP_STORAGE_URI`` (KServe の ``STORAGE_URI`` ではない)。
    Phase 5 Run 6 で encoder server が読む env 名と manifest の env 名が
    食い違うと container が startup で exit する事故が発生したため、ここでも
    同じ名前で揃える。trailing slash は GcsPrefix.parse が strip するが、
    list_blobs が directory として扱うため `/` を補ってから patch する。
    """
    normalized = storage_uri.rstrip("/") + "/"
    patch: dict[str, Any] = {
        "spec": {
            "predictor": {
                "containers": [
                    {
                        "name": "kserve-container",
                        "env": [
                            {"name": "AIP_STORAGE_URI", "value": normalized},
                        ],
                    }
                ]
            }
        }
    }
    run(
        [
            "kubectl",
            "patch",
            "inferenceservice",
            "property-encoder",
            f"--namespace={NAMESPACE}",
            "--type=merge",
            f"--patch={json.dumps(patch)}",
        ]
    )


def _wait_ready(name: str) -> None:
    proc = run(
        [
            "kubectl",
            "wait",
            f"inferenceservice/{name}",
            f"--namespace={NAMESPACE}",
            "--for=condition=Ready",
            f"--timeout={ROLLOUT_TIMEOUT_SEC}s",
        ],
        capture=True,
        check=False,
    )
    if proc.returncode != 0:
        print(
            f"[error] {name} did not become Ready within {ROLLOUT_TIMEOUT_SEC}s",
            file=sys.stderr,
        )
        raise SystemExit(1)


def main() -> int:
    project_id = _require("PROJECT_ID")
    region = env("REGION", "asia-northeast1")

    encoder = _resolve_latest("property-encoder", project_id=project_id, region=region)
    reranker = _resolve_latest("property-reranker", project_id=project_id, region=region)
    print(f"[info] encoder version={encoder.version_id} uri={encoder.artifact_uri}")
    print(f"[info] reranker version={reranker.version_id} uri={reranker.artifact_uri}")

    _patch_encoder_storage_uri(encoder.artifact_uri)
    _patch_reranker_storage_uri(reranker.artifact_uri)

    _wait_ready("property-encoder")
    _wait_ready("property-reranker")
    print("[ok] KServe InferenceService updated to latest registry versions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
