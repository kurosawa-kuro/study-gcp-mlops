"""Local alternative to .github/workflows/deploy-api.yml (Phase 6 / GKE).

Builds the search-api image via Cloud Build, pushes to Artifact Registry,
then patches the GKE Deployment (`deployment/search-api` in namespace
`search`) to roll the new image.

Safety rules:
- never delete tags before push;
- always build/deploy an immutable tag (`<sha>-<epoch>`);
- fail fast with diagnostics when Cloud Build / kubectl rollout fails.
"""

from __future__ import annotations

import subprocess
import sys
import time

from scripts._common import env, run, submit_cloud_build_async, wait_cloud_build

BUILD_TIMEOUT_SEC = 900
ROLLOUT_TIMEOUT_SEC = 300
NAMESPACE = "search"
DEPLOYMENT = "search-api"
CONTAINER = "search-api"


def _diag(label: str, proc: subprocess.CompletedProcess[str]) -> None:
    print(f"[diag] {label} exit={proc.returncode}", file=sys.stderr)
    if proc.stdout:
        print(proc.stdout.rstrip(), file=sys.stderr)


def _require(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"[error] required env var {name} is empty")
    return value


def _ensure_kubectl_context(cluster_name: str, region: str, project_id: str) -> None:
    proc = run(["kubectl", "config", "current-context"], capture=True, check=False)
    current = (proc.stdout or "").strip()
    if cluster_name not in current:
        print(
            f"[info] kubectl context '{current}' does not reference '{cluster_name}'. "
            "Fetching credentials...",
            file=sys.stderr,
        )
        run(
            [
                "gcloud",
                "container",
                "clusters",
                "get-credentials",
                cluster_name,
                f"--region={region}",
                f"--project={project_id}",
            ]
        )


def main() -> int:
    project_id = _require("PROJECT_ID")
    region = env("REGION", "asia-northeast1")
    cluster_name = env("GKE_CLUSTER_NAME", "hybrid-search")
    artifact_repo = env("ARTIFACT_REPO_ID", "mlops")
    sha = _require("GIT_SHA")

    image_tag = f"{sha}-{int(time.time())}"
    image_uri = f"{region}-docker.pkg.dev/{project_id}/{artifact_repo}/search-api:{image_tag}"

    _ensure_kubectl_context(cluster_name, region, project_id)

    build_id = submit_cloud_build_async(
        project_id=project_id,
        config="cloudbuild.api.yaml",
        substitutions=f"_IMAGE_URI={image_uri}",
    )
    wait_cloud_build(
        project_id=project_id,
        build_id=build_id,
        timeout_sec=BUILD_TIMEOUT_SEC,
    )

    run(
        [
            "kubectl",
            "set",
            "image",
            f"deployment/{DEPLOYMENT}",
            f"{CONTAINER}={image_uri}",
            f"--namespace={NAMESPACE}",
        ]
    )
    proc = run(
        [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{DEPLOYMENT}",
            f"--namespace={NAMESPACE}",
            f"--timeout={ROLLOUT_TIMEOUT_SEC}s",
        ],
        capture=True,
        check=False,
    )
    if proc.returncode != 0:
        _diag("kubectl rollout status", proc)
        return 1
    print(f"[ok] search-api rolled out image={image_uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
