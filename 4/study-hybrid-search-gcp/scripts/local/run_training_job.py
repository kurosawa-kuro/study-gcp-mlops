"""Execute Cloud Run Job `training-job` once and wait for completion.

This script is used as the model-first gate in deploy-all:
deploy/update training-job image -> execute job once -> then deploy API.
"""

from __future__ import annotations

from scripts._common import env, run

# PDCA fail-fast policy:
# - Timeout extension is forbidden.
# - A timeout indicates likely bug/config regression, so we fail immediately.
# Successful runs complete well before 6 minutes; keep a safety margin.
EXEC_TIMEOUT_SEC = 360


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("REGION")
    job = env("TRAINING_JOB")

    print(f"==> Execute {job} and wait (timeout={EXEC_TIMEOUT_SEC}s)", flush=True)
    run(
        [
            "gcloud",
            "run",
            "jobs",
            "execute",
            job,
            f"--project={project_id}",
            f"--region={region}",
            "--wait",
        ],
        timeout=EXEC_TIMEOUT_SEC,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
