"""Sync model artifacts from Vertex Model Registry into KServe InferenceService.

For each of the encoder and reranker, this script:
1. Resolves the latest production-alias Model version in Vertex Model Registry
2. Extracts the GCS artifact URI
3. Patches the corresponding `InferenceService` in namespace `kserve-inference`
   so that `spec.predictor.model.storageUri` (reranker) or
   `spec.predictor.containers[0].env[AIP_STORAGE_URI]` (encoder) points at the new URI

Phase 6 keeps the training pipeline unchanged — Vertex Model Registry remains
the canonical distribution point. Only the deployment target switches from
Vertex Endpoint to KServe InferenceService.

**過去事故の再発検知用ログ**:

* Phase 5 Run 5 で `aiplatform.Model.upload` が serving image の存在を 404
  検証する挙動に気付かず詰まった教訓から、resolve した artifact_uri / version_id /
  aliases を全て STDOUT に echo してから patch へ進む。
* Phase 5 Run 6 で encoder が `AIP_STORAGE_URI` を読まず起動失敗した際に、どの
  env 名でどの値を patch したか不明で詰まった。ここでは patch JSON を丸ごと
  STDOUT に echo する。
* `kubectl wait --for=condition=Ready` が失敗した時は、直後に `kubectl get
  inferenceservice` / `kubectl describe` / `kubectl get events` / `kubectl
  logs` をまとめて吐き出して即座にトリアージできるようにする。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from scripts._common import env, run

NAMESPACE = "kserve-inference"
ROLLOUT_TIMEOUT_SEC = 600


def _step(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def _info(msg: str) -> None:
    print(f"[info] {msg}", flush=True)


def _error(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr, flush=True)


@dataclass
class ModelVersion:
    display_name: str
    version_id: str
    artifact_uri: str
    aliases: list[str]


def _require(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"[error] required env var {name} is empty")
    return value


def _resolve_latest(display_name: str, *, project_id: str, region: str) -> ModelVersion:
    """Resolve the 'production' alias (or most recent) version from Model Registry."""
    _step(f"resolve_latest display_name={display_name!r} project={project_id} region={region}")
    try:
        from google.cloud import aiplatform
    except ImportError:
        _error("google-cloud-aiplatform not installed. run `make sync` first.")
        raise

    aiplatform.init(project=project_id, location=region)
    models = aiplatform.Model.list(filter=f'display_name="{display_name}"')
    _info(f"Model Registry returned {len(models)} candidate(s) for display_name={display_name!r}")
    if not models:
        _error(
            f"No model with display_name={display_name}. "
            f"Run `make ops-train-now` → `scripts.local.ops.register_model --apply` "
            f"to populate Model Registry first."
        )
        raise RuntimeError(f"No model with display_name={display_name}")

    # Enumerate every candidate so operators can see which version we landed on
    for idx, candidate in enumerate(models):
        aliases = list(getattr(candidate, "version_aliases", []) or [])
        _info(
            f"  [{idx}] version_id={candidate.version_id} aliases={aliases} "
            f"uri={getattr(candidate, 'uri', '?')}"
        )

    model = models[0]
    for candidate in models:
        aliases = getattr(candidate, "version_aliases", []) or []
        if "production" in aliases:
            model = candidate
            _info(f"selected version_id={model.version_id} (via `production` alias)")
            break
    else:
        _info(
            f"no `production` alias found — falling back to first (version_id={model.version_id}). "
            "Run `make ops-promote-reranker` / equivalent to set production alias."
        )

    artifact_uri = getattr(model, "uri", None) or getattr(model._gca_resource, "artifact_uri", "")
    aliases = list(getattr(model, "version_aliases", []) or [])
    if not artifact_uri:
        _error(
            f"Model {display_name} (version={model.version_id}) has no artifact_uri — "
            "upload was incomplete."
        )
        raise RuntimeError(f"Model {display_name} (version={model.version_id}) has no artifact_uri")
    resolved = ModelVersion(
        display_name=display_name,
        version_id=str(model.version_id),
        artifact_uri=str(artifact_uri),
        aliases=aliases,
    )
    _info(
        f"RESOLVED {display_name} version={resolved.version_id} "
        f"aliases={resolved.aliases} artifact_uri={resolved.artifact_uri}"
    )
    return resolved


def _kubectl_patch(isvc_name: str, patch: dict[str, Any]) -> None:
    """Run `kubectl patch inferenceservice` with full echo of the applied patch."""
    patch_json = json.dumps(patch)
    _info(f"kubectl patch inferenceservice/{isvc_name} -n {NAMESPACE} patch={patch_json}")
    proc = run(
        [
            "kubectl",
            "patch",
            "inferenceservice",
            isvc_name,
            f"--namespace={NAMESPACE}",
            "--type=merge",
            f"--patch={patch_json}",
        ],
        capture=True,
        check=False,
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        _error(
            f"kubectl patch FAILED for inferenceservice/{isvc_name} rc={proc.returncode}. "
            f"Verify InferenceService exists: `kubectl get isvc -n {NAMESPACE}`."
        )
        raise SystemExit(proc.returncode)


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
    _kubectl_patch("property-reranker", patch)


def _patch_encoder_storage_uri(storage_uri: str) -> None:
    """Encoder uses a custom Python predictor (Vertex CPR 規約を継承) —
    env var 名は ``AIP_STORAGE_URI`` (KServe の ``STORAGE_URI`` ではない)。
    Phase 5 Run 6 で encoder server が読む env 名と manifest の env 名が
    食い違うと container が startup で exit する事故が発生したため、ここでも
    同じ名前で揃える。trailing slash は GcsPrefix.parse が strip するが、
    list_blobs が directory として扱うため `/` を補ってから patch する。
    """
    normalized = storage_uri.rstrip("/") + "/"
    if normalized != storage_uri:
        _info(f"encoder storageUri normalized to trailing slash: {storage_uri!r} → {normalized!r}")
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
    _kubectl_patch("property-encoder", patch)


def _dump_diagnostics(name: str) -> None:
    """Dump kubectl get / describe / events / logs so failures are triageable."""
    _error(f"---- diagnostics for inferenceservice/{name} (namespace={NAMESPACE}) ----")
    for cmd in (
        ["kubectl", "get", "inferenceservice", name, f"--namespace={NAMESPACE}", "-o", "yaml"],
        ["kubectl", "describe", "inferenceservice", name, f"--namespace={NAMESPACE}"],
        [
            "kubectl",
            "get",
            "pods",
            f"--namespace={NAMESPACE}",
            "-l",
            f"serving.kserve.io/inferenceservice={name}",
        ],
        [
            "kubectl",
            "get",
            "events",
            f"--namespace={NAMESPACE}",
            "--sort-by=.lastTimestamp",
            "--field-selector",
            f"involvedObject.name={name}",
        ],
        # best-effort pod logs (tail 200 across all pods for this ISVC)
        [
            "kubectl",
            "logs",
            f"--namespace={NAMESPACE}",
            "-l",
            f"serving.kserve.io/inferenceservice={name}",
            "--all-containers=true",
            "--tail=200",
        ],
    ):
        _error(f"$ {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.stdout:
            sys.stderr.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        sys.stderr.flush()


def _wait_ready(name: str) -> None:
    _step(f"wait inferenceservice/{name} for condition=Ready timeout={ROLLOUT_TIMEOUT_SEC}s")
    start = time.monotonic()
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
    elapsed = time.monotonic() - start
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        _error(
            f"{name} did not become Ready within {ROLLOUT_TIMEOUT_SEC}s "
            f"(actual elapsed={elapsed:.0f}s). Dumping diagnostics..."
        )
        _dump_diagnostics(name)
        raise SystemExit(1)
    _info(f"inferenceservice/{name} Ready elapsed={elapsed:.0f}s")


def main() -> int:
    project_id = _require("PROJECT_ID")
    region = env("REGION", "asia-northeast1")

    _step(f"kserve_models sync start project={project_id} region={region} namespace={NAMESPACE}")

    encoder = _resolve_latest("property-encoder", project_id=project_id, region=region)
    reranker = _resolve_latest("property-reranker", project_id=project_id, region=region)
    _info(f"encoder version={encoder.version_id} uri={encoder.artifact_uri}")
    _info(f"reranker version={reranker.version_id} uri={reranker.artifact_uri}")

    _step("patch encoder storage URI (via env AIP_STORAGE_URI)")
    _patch_encoder_storage_uri(encoder.artifact_uri)
    _step("patch reranker storage URI (via spec.predictor.model.storageUri)")
    _patch_reranker_storage_uri(reranker.artifact_uri)

    _wait_ready("property-encoder")
    _wait_ready("property-reranker")
    _step("kserve_models sync DONE — InferenceService updated to latest registry versions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
