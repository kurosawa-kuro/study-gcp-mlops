"""Local alternative to .github/workflows/deploy-training-job.yml.

Kept for compatibility even though training moved to Vertex Pipelines.
Uses immutable tags and fail-fast cloud-build waiting.
"""

from __future__ import annotations

import time

from scripts._common import env, run, submit_cloud_build_async, wait_cloud_build

BUILD_TIMEOUT_SEC = 480
UPDATE_TIMEOUT_SEC = 180


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("REGION")
    artifact_repo = env("ARTIFACT_REPO")
    job = env("TRAINING_JOB")

    sha = run(["git", "rev-parse", "--short=8", "HEAD"], capture=True).stdout.strip()
    build_tag = f"{sha}-{int(time.time())}"
    image_path = f"{region}-docker.pkg.dev/{project_id}/{artifact_repo}/{job}"
    uri = f"{image_path}:{build_tag}"

    print(f"==> Cloud Build submit {uri}", flush=True)
    build_id = submit_cloud_build_async(
        project_id=project_id,
        config="cloudbuild.train.yaml",
        substitutions=f"_URI={uri}",
    )
    print(f"==> Cloud Build wait id={build_id} timeout={BUILD_TIMEOUT_SEC}s", flush=True)
    wait_cloud_build(project_id=project_id, build_id=build_id, timeout_sec=BUILD_TIMEOUT_SEC)

    print(f"==> Update {job}", flush=True)
    run(
        [
            "gcloud",
            "run",
            "jobs",
            "update",
            job,
            f"--project={project_id}",
            f"--region={region}",
            f"--image={uri}",
            f"--service-account=sa-job-train@{project_id}.iam.gserviceaccount.com",
            f"--set-env-vars=PROJECT_ID={project_id},GIT_SHA={build_tag}",
        ],
        timeout=UPDATE_TIMEOUT_SEC,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
