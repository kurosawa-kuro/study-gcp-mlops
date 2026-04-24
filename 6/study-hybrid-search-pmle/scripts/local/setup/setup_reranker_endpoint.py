"""Register + deploy the Vertex AI reranker Model onto its Endpoint.

Phase 6 Run 1 で学んだ教訓:
  `scripts/local/ops/register_model.py` は SUCCEEDED pipeline run 前提
  (pipeline-root bucket から `train-reranker_*/executor_output.json` を探しに
  いく)。destroy-all 直後で pipeline が一度も回っていない partial-reset 状態で
  は reranker endpoint を復元する手段がなく、やむなく一時スクリプト
  `/tmp/phase6-deploy-reranker.py` を手書きで復元していた。

このモジュールはその一時スクリプトを恒久化し、
``setup_encoder_endpoint.py`` と同じ ``build_endpoint_spec`` / ``_apply``
シグネチャで reranker を扱えるようにする。

Pipeline 経由の Model.upload は従来どおり ``register_model.py`` を使える。
このモジュールは **GCS artifact (gs://{bucket}/reranker/v1/model.txt) が既に
ある前提** の direct-register ルートを担当する (smoke モデル / manual upload
/ Run 1 の復元手順)。

Default は:
  artifact_uri = gs://{PROJECT_ID}-models/reranker/v1/
  image        = {REGION}-docker.pkg.dev/{PROJECT_ID}/{REPO}/property-reranker:latest
  machine      = n1-standard-2 (min=max=1, 学習リポ minimum spec 準拠)
  service_account = sa-endpoint-reranker@{PROJECT_ID}.iam.gserviceaccount.com
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from scripts._common import env

DEFAULT_MACHINE_TYPE: str = "n1-standard-2"
DEFAULT_MIN_REPLICAS: int = 1
DEFAULT_MAX_REPLICAS: int = 1  # 学習リポは常に min=max=1
DEFAULT_ASSET_VERSION: str = "v1"


def _artifact_registry_image(project_id: str, region: str, repo: str, tag: str) -> str:
    return f"{region}-docker.pkg.dev/{project_id}/{repo}/property-reranker:{tag}"


def build_endpoint_spec() -> dict[str, Any]:
    """Resolve the Model-upload + Endpoint-deploy spec without SDK calls."""
    project_id = env("PROJECT_ID")
    region = env("VERTEX_LOCATION", env("REGION"))
    repo = env("ARTIFACT_REPO", "mlops")
    image_tag = env("RERANKER_IMAGE_TAG", "latest")
    bucket = env("GCS_MODELS_BUCKET", f"{project_id}-models" if project_id else "")
    version = env("RERANKER_ASSET_VERSION", DEFAULT_ASSET_VERSION)
    artifact_prefix = f"reranker/{version}/"
    return {
        "project_id": project_id,
        "vertex_location": region,
        "endpoint_display_name": env(
            "RERANKER_ENDPOINT_DISPLAY_NAME", "property-reranker-endpoint"
        ),
        "model_display_name": env("RERANKER_MODEL_DISPLAY_NAME", "property-reranker"),
        "serving_container_image_uri": _artifact_registry_image(
            project_id, region, repo, image_tag
        ),
        "serving_container_predict_route": "/predict",
        "serving_container_health_route": "/health",
        "serving_container_ports": [8080],
        "artifact_uri": f"gs://{bucket}/{artifact_prefix}" if bucket else "",
        "machine_type": env("RERANKER_MACHINE_TYPE", DEFAULT_MACHINE_TYPE),
        "min_replica_count": int(env("RERANKER_MIN_REPLICAS", str(DEFAULT_MIN_REPLICAS))),
        "max_replica_count": int(env("RERANKER_MAX_REPLICAS", str(DEFAULT_MAX_REPLICAS))),
        "service_account": env(
            "RERANKER_ENDPOINT_SERVICE_ACCOUNT",
            f"sa-endpoint-reranker@{project_id}.iam.gserviceaccount.com" if project_id else "",
        ),
        "model_alias": env("RERANKER_MODEL_ALIAS", "staging"),
        "traffic_percentage": int(env("RERANKER_TRAFFIC_PERCENTAGE", "100")),
    }


def _get_or_create_endpoint(aiplatform: Any, spec: dict[str, Any]) -> Any:
    existing = aiplatform.Endpoint.list(
        filter=f'display_name="{spec["endpoint_display_name"]}"',
        project=spec["project_id"],
        location=spec["vertex_location"],
    )
    if existing:
        return existing[0]
    return aiplatform.Endpoint.create(
        display_name=spec["endpoint_display_name"],
        project=spec["project_id"],
        location=spec["vertex_location"],
    )


def _apply(spec: dict[str, Any]) -> dict[str, Any]:
    import sys
    import traceback

    def _log(msg: str) -> None:
        print(f"[setup_reranker] {msg}", flush=True)
        print(f"[setup_reranker] {msg}", file=sys.stderr, flush=True)

    _log("STEP 1 — validate spec")
    _log(f"  artifact_uri={spec['artifact_uri']!r}")
    _log(f"  serving_container_image_uri={spec['serving_container_image_uri']!r}")
    _log(f"  machine_type={spec['machine_type']}")
    _log(
        f"  min_replica_count={spec['min_replica_count']} "
        f"max_replica_count={spec['max_replica_count']}"
    )
    _log(f"  service_account={spec['service_account']!r}")
    _log(f"  endpoint_display_name={spec['endpoint_display_name']}")
    _log(f"  model_display_name={spec['model_display_name']}")

    if not spec["artifact_uri"]:
        raise RuntimeError(
            "artifact_uri is empty; upload model.txt to "
            "gs://{PROJECT_ID}-models/reranker/v1/model.txt first"
        )
    try:
        _log("STEP 2 — import aiplatform + init")
        from google.cloud import aiplatform

        aiplatform.init(project=spec["project_id"], location=spec["vertex_location"])

        _log("STEP 3 — aiplatform.Model.upload")
        model = aiplatform.Model.upload(
            display_name=spec["model_display_name"],
            serving_container_image_uri=spec["serving_container_image_uri"],
            serving_container_predict_route=spec["serving_container_predict_route"],
            serving_container_health_route=spec["serving_container_health_route"],
            serving_container_ports=spec["serving_container_ports"],
            artifact_uri=spec["artifact_uri"],
            version_aliases=[spec["model_alias"]],
            sync=True,
        )
        _log(f"  Model.upload OK resource={model.resource_name} version={model.version_id}")

        _log("STEP 4 — get or create endpoint")
        endpoint = _get_or_create_endpoint(aiplatform, spec)
        _log(f"  endpoint resource={endpoint.resource_name}")

        _log("STEP 5 — Model.deploy")
        model.deploy(
            endpoint=endpoint,
            machine_type=spec["machine_type"],
            min_replica_count=spec["min_replica_count"],
            max_replica_count=spec["max_replica_count"],
            traffic_percentage=spec["traffic_percentage"],
            service_account=spec["service_account"],
            sync=True,
        )
        _log("  Model.deploy OK")
    except Exception:
        _log(
            "ERROR in _apply — candidates: (H1) artifact_uri 先に model.txt が未配置、"
            "(H2) sa-endpoint-reranker が models bucket を read 不可、"
            "(H3) property-reranker:latest image が未 push / tag 外れ"
        )
        _log(traceback.format_exc())
        raise
    return {
        "endpoint_resource_name": endpoint.resource_name,
        "model_resource_name": model.resource_name,
        "model_version_id": model.version_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register + deploy the Vertex AI reranker Model onto its Endpoint. "
            "Direct-register route (requires pre-uploaded model.txt in GCS). "
            "For pipeline-driven registration, use scripts.local.ops.register_model."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually call aiplatform.Model.upload + Endpoint.deploy (requires auth).",
    )
    args = parser.parse_args()

    spec = build_endpoint_spec()
    print(json.dumps(spec, ensure_ascii=False, indent=2))
    if args.apply:
        result = _apply(spec)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
