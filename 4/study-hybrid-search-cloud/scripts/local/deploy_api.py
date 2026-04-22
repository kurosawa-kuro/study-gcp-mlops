"""Local alternative to .github/workflows/deploy-api.yml — builds search-api
via Cloud Build and rolls out a Cloud Run revision. Invoked by
`make deploy-api-local` (and indirectly by `make deploy-all`).

Safety rule:
- Never delete tags before push. It can create a "tag missing" race where
  deploy happens while a rebuild is still WORKING.
- Always push an immutable tag (`<git-sha>-<epoch>`) and deploy that exact
  tag after Cloud Build SUCCESS.
"""

from __future__ import annotations

import subprocess
import sys
import time

from scripts._common import env, run, submit_cloud_build_async, wait_cloud_build

ENV_VARS = ",".join(
    [
        "PROJECT_ID={project_id}",
        "GCS_MODELS_BUCKET={project_id}-models",
        "RANKING_LOG_TOPIC=ranking-log",
        "FEEDBACK_TOPIC=search-feedback",
        "RETRAIN_TOPIC=retrain-trigger",
        "ENABLE_SEARCH=true",
        "ENCODER_MODEL_DIR=intfloat/multilingual-e5-base",
        "MEILI_BASE_URL={meili_base_url}",
        "MEILI_REQUIRE_IDENTITY_TOKEN=false",
        "LOG_AS_JSON=1",
        "GCP_LOGGING_ENABLED=1",
    ]
)

# PDCA fail-fast policy:
# - Timeout is fixed from observed successful runs, not ad-hoc extension.
# - search-api Cloud Build (docker build + push) recently takes ~625-805s
#   in this project, so 810s is the current shortest safe window.
BUILD_TIMEOUT_SEC = 810
# - Cloud Run deploy usually converges within ~1 min. Keep a small buffer.
DEPLOY_TIMEOUT_SEC = 120


def _print_cmd_output(label: str, proc: subprocess.CompletedProcess[str]) -> None:
    """Print captured command output for fast triage."""
    print(f"[diag] {label} exit_code={proc.returncode}", file=sys.stderr)
    if proc.stdout:
        print(f"[diag] {label} stdout:", file=sys.stderr)
        print(proc.stdout.rstrip(), file=sys.stderr)
    if proc.stderr:
        print(f"[diag] {label} stderr:", file=sys.stderr)
        print(proc.stderr.rstrip(), file=sys.stderr)


def _diag_context(project_id: str, region: str, service: str, image_path: str, uri: str) -> None:
    """Print execution context to detect project/region/service mismatch quickly."""
    print("[diag] deploy context", file=sys.stderr)
    print(f"[diag] PROJECT_ID={project_id}", file=sys.stderr)
    print(f"[diag] REGION={region}", file=sys.stderr)
    print(f"[diag] API_SERVICE={service}", file=sys.stderr)
    print(f"[diag] IMAGE_PATH={image_path}", file=sys.stderr)
    print(f"[diag] IMAGE_URI={uri}", file=sys.stderr)
    proc = subprocess.run(
        ["gcloud", "config", "list", "--format=text(core.project,core.account,run.region)"],
        check=False,
        text=True,
        capture_output=True,
    )
    _print_cmd_output("gcloud-config", proc)


def _diag_service_state(project_id: str, region: str, service: str, *, stage: str) -> None:
    """Dump service image/revision/traffic to verify whether deploy took effect."""
    proc = subprocess.run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            service,
            f"--project={project_id}",
            f"--region={region}",
            "--format=value(spec.template.spec.containers[0].image,status.latestReadyRevisionName,status.traffic)",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    _print_cmd_output(f"service-state-{stage}", proc)


def _diag_recent_revisions(project_id: str, region: str, service: str) -> None:
    """Dump latest revisions so deploy/no-deploy can be judged immediately."""
    proc = subprocess.run(
        [
            "gcloud",
            "run",
            "revisions",
            "list",
            f"--project={project_id}",
            f"--region={region}",
            f"--service={service}",
            "--limit=5",
            "--format=value(metadata.name,status.conditions[0].status,metadata.creationTimestamp,spec.containers[0].image)",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    _print_cmd_output("recent-revisions", proc)


def _diag_image_digest(project_id: str, image_path: str, tag: str) -> None:
    """Print pushed digest for a tag to detect tag/digest mismatch quickly."""
    proc = subprocess.run(
        [
            "gcloud",
            "artifacts",
            "docker",
            "tags",
            "list",
            image_path,
            f"--project={project_id}",
            "--filter",
            f"tag:{tag}",
            "--format=value(tag,digest,create_time)",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    _print_cmd_output("artifact-tag-digest", proc)


def _assert_model_ready(project_id: str) -> None:
    """Fail if no finished training run exists (model-first gate)."""
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
    # CSV output: header + value
    finished_runs = int(lines[-1]) if lines else 0
    if finished_runs <= 0:
        raise RuntimeError(
            "model-first gate failed: no finished training run found in "
            f"`{project_id}.mlops.training_runs`; deploy training-job and execute it first"
        )


def _resolve_meili_base_url(project_id: str, region: str) -> str:
    url = run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            "meili-search",
            f"--project={project_id}",
            f"--region={region}",
            "--format=value(status.url)",
        ],
        capture=True,
    ).stdout.strip()
    if not url:
        raise RuntimeError("failed to resolve meili-search Cloud Run URL")
    return url


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("REGION")
    artifact_repo = env("ARTIFACT_REPO")
    service = env("API_SERVICE")
    meili_base_url = _resolve_meili_base_url(project_id, region)

    print("==> Verify model-first gate (training_runs has finished run)", flush=True)
    _assert_model_ready(project_id)

    sha = run(["git", "rev-parse", "--short=8", "HEAD"], capture=True).stdout.strip()
    build_tag = f"{sha}-{int(time.time())}"
    image_path = f"{region}-docker.pkg.dev/{project_id}/{artifact_repo}/{service}"
    uri = f"{image_path}:{build_tag}"
    _diag_context(project_id, region, service, image_path, uri)
    _diag_service_state(project_id, region, service, stage="before-build")

    print(f"==> Cloud Build submit {uri}", flush=True)
    build_id = submit_cloud_build_async(
        project_id=project_id,
        config="infra/run/services/search_api/cloudbuild.yaml",
        substitutions=f"_URI={uri}",
    )
    print(f"==> Cloud Build wait id={build_id} timeout={BUILD_TIMEOUT_SEC}s", flush=True)
    wait_cloud_build(
        project_id=project_id,
        build_id=build_id,
        timeout_sec=BUILD_TIMEOUT_SEC,
    )
    _diag_image_digest(project_id, image_path, build_tag)
    _diag_service_state(project_id, region, service, stage="before-deploy")

    print(f"==> Deploy {service}", flush=True)
    deploy_cmd = [
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
        "--no-allow-unauthenticated",
        f"--set-env-vars={ENV_VARS.format(project_id=project_id, meili_base_url=meili_base_url)}",
        f"--labels=git-sha={sha}",
    ]
    try:
        deploy_proc = subprocess.run(
            deploy_cmd,
            check=False,
            text=True,
            capture_output=True,
            timeout=DEPLOY_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"[diag] run-deploy timeout after {DEPLOY_TIMEOUT_SEC}s "
            f"(treat as fail-fast bug signal): {exc}",
            file=sys.stderr,
        )
        _diag_service_state(project_id, region, service, stage="after-timeout")
        _diag_recent_revisions(project_id, region, service)
        raise RuntimeError(
            f"gcloud run deploy {service} exceeded timeout ({DEPLOY_TIMEOUT_SEC}s)"
        ) from exc
    _print_cmd_output("run-deploy", deploy_proc)
    if deploy_proc.returncode != 0:
        _diag_service_state(project_id, region, service, stage="after-deploy-fail")
        _diag_recent_revisions(project_id, region, service)
        raise RuntimeError(f"gcloud run deploy {service} failed with exit={deploy_proc.returncode}")

    _diag_service_state(project_id, region, service, stage="after-deploy")
    _diag_recent_revisions(project_id, region, service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
