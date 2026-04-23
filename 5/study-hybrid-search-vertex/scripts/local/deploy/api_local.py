"""Local alternative to .github/workflows/deploy-api.yml.

Safety rules:
- never delete tags before push;
- always build/deploy an immutable tag (`<sha>-<epoch>`);
- fail fast with diagnostics when Cloud Build / Cloud Run deploy fails.
"""

from __future__ import annotations

import subprocess
import sys
import time

from scripts._common import env, run, submit_cloud_build_async, wait_cloud_build

BUILD_TIMEOUT_SEC = 900
DEPLOY_TIMEOUT_SEC = 180


def _assert_model_ready(project_id: str) -> None:
    query = (
        "SELECT COUNT(1) "
        f"FROM `{project_id}.mlops.training_runs` "
        "WHERE finished_at IS NOT NULL"
    )
    proc = run(
        [
            "bq",
            "query",
            "--use_legacy_sql=false",
            f"--project_id={project_id}",
            "--format=csv",
            query,
        ],
        capture=True,
    )
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    finished_runs = int(lines[-1]) if lines else 0
    if finished_runs <= 0:
        raise RuntimeError(
            "model-first gate failed: no finished training run found in "
            f"`{project_id}.mlops.training_runs`"
        )


def _diag(label: str, proc: subprocess.CompletedProcess[str]) -> None:
    print(f"[diag] {label} exit={proc.returncode}", file=sys.stderr)
    if proc.stdout:
        print(proc.stdout.rstrip(), file=sys.stderr)
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)


def _require_non_empty_env(name: str) -> str:
    value = env(name).strip()
    if not value:
        raise RuntimeError(f"{name} must be set before deploy")
    return value


def _build_env_vars(*, project_id: str) -> str:
    vertex_location = env("VERTEX_LOCATION", "asia-northeast1").strip() or "asia-northeast1"
    encoder_endpoint_id = _require_non_empty_env("VERTEX_ENCODER_ENDPOINT_ID")
    reranker_endpoint_id = env("VERTEX_RERANKER_ENDPOINT_ID", "").strip()
    enable_rerank = "true" if reranker_endpoint_id else "false"
    return ",".join(
        [
            f"PROJECT_ID={project_id}",
            f"GCS_MODELS_BUCKET={project_id}-models",
            "RANKING_LOG_TOPIC=ranking-log",
            "FEEDBACK_TOPIC=search-feedback",
            "RETRAIN_TOPIC=retrain-trigger",
            "ENABLE_SEARCH=true",
            f"ENABLE_RERANK={enable_rerank}",
            f"VERTEX_LOCATION={vertex_location}",
            f"VERTEX_ENCODER_ENDPOINT_ID={encoder_endpoint_id}",
            f"VERTEX_RERANKER_ENDPOINT_ID={reranker_endpoint_id}",
            "LOG_AS_JSON=1",
            "GCP_LOGGING_ENABLED=1",
        ]
    )


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("REGION")
    artifact_repo = env("ARTIFACT_REPO")
    service = env("API_SERVICE")
    env_vars = _build_env_vars(project_id=project_id)

    _assert_model_ready(project_id)

    sha = run(["git", "rev-parse", "--short=8", "HEAD"], capture=True).stdout.strip()
    build_tag = f"{sha}-{int(time.time())}"
    image_path = f"{region}-docker.pkg.dev/{project_id}/{artifact_repo}/{service}"
    uri = f"{image_path}:{build_tag}"

    print(f"==> Cloud Build submit {uri}", flush=True)
    build_id = submit_cloud_build_async(
        project_id=project_id,
        config="cloudbuild.api.yaml",
        substitutions=f"_URI={uri}",
    )
    print(f"==> Cloud Build wait id={build_id} timeout={BUILD_TIMEOUT_SEC}s", flush=True)
    wait_cloud_build(project_id=project_id, build_id=build_id, timeout_sec=BUILD_TIMEOUT_SEC)

    print(f"==> Deploy {service}", flush=True)
    deploy_proc = subprocess.run(
        [
            "gcloud",
            "run",
            "deploy",
            service,
            f"--project={project_id}",
            f"--region={region}",
            f"--image={uri}",
            f"--service-account=sa-api@{project_id}.iam.gserviceaccount.com",
            "--cpu=2",
            "--memory=4Gi",
            "--concurrency=80",
            "--min-instances=1",
            "--max-instances=10",
            "--cpu-boost",
            "--execution-environment=gen2",
            "--allow-unauthenticated",
            f"--set-env-vars={env_vars}",
            f"--labels=git-sha={sha}",
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=DEPLOY_TIMEOUT_SEC,
    )
    _diag("run-deploy", deploy_proc)
    if deploy_proc.returncode != 0:
        raise RuntimeError(f"gcloud run deploy {service} failed with exit={deploy_proc.returncode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
