"""Vertex AI Endpoint cleanup helpers for destroy-all.

Terraform-managed `google_vertex_ai_endpoint` は empty shell。
`aiplatform.Model.deploy()` (KFP components / scripts) が server-side で
`deployedModels` を埋めるため、Terraform 側からは見えない。残っていると
`terraform destroy` が HTTP 400 ``Endpoint has deployed or being-deployed
DeployedModel(s)`` で fail するので、本 module で undeploy する。

Phase 7 では KServe に serving 移譲しており Vertex Endpoint は完全に
shell として残置 — ただし Phase 6 までの canonical 経路を継承する設計上、
リソースとしては存在する (`scripts/lib/gcp_resources.VERTEX_ENDPOINTS`)。
"""

from __future__ import annotations

import json
import subprocess

from scripts._common import env, run
from scripts.lib.gcp_resources import VERTEX_ENDPOINTS


def undeploy_endpoint_models(project_id: str, region: str, endpoint: str) -> None:
    """Synchronously undeploy every DeployedModel on one endpoint.

    Benign when the endpoint does not exist yet (fresh project / already
    torn down) — we detect that via `gcloud describe` returning non-zero.
    `gcloud ... undeploy-model --quiet` waits for the long-running op,
    so control returns only when the deployed_model is fully detached.
    """
    proc = subprocess.run(
        [
            "gcloud",
            "ai",
            "endpoints",
            "describe",
            endpoint,
            f"--region={region}",
            f"--project={project_id}",
            "--format=json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"    endpoint {endpoint!r} not present — skip")
        return
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    deployed = payload.get("deployedModels") or []
    if not deployed:
        print(f"    endpoint {endpoint!r} has no deployed_models — skip")
        return
    for dm in deployed:
        dm_id = dm["id"]
        display = dm.get("displayName", "?")
        print(f"    undeploy-model {endpoint} id={dm_id} display={display}")
        run(
            [
                "gcloud",
                "ai",
                "endpoints",
                "undeploy-model",
                endpoint,
                f"--deployed-model-id={dm_id}",
                f"--region={region}",
                f"--project={project_id}",
                "--quiet",
            ]
        )


def undeploy_all_endpoint_shells(project_id: str | None = None, region: str | None = None) -> None:
    """Iterate `VERTEX_ENDPOINTS` and detach all DeployedModels."""
    pid = project_id or env("PROJECT_ID")
    rgn = region or env("VERTEX_LOCATION") or env("REGION")
    for endpoint in VERTEX_ENDPOINTS:
        undeploy_endpoint_models(pid, rgn, endpoint)
