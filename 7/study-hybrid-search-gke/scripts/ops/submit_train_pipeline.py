"""Vertex train pipeline compile+submit for Composer `KubernetesPodOperator` (V5-8).

`retrain_orchestration` used to call `python -m pipeline.workflow.compile` with
argv containing shell-style ``$(GCP_PROJECT)`` strings. The pod receives those
literals (no shell expansion) and Vertex / KFP then fail in confusing ways. A
separate failure mode was ``FileNotFoundError: 'dist/pipelines'`` when the
process cwd or permissions did not match local `make` runs.

This entrypoint runs **inside composer-runner** at task execution time, reads
``GCP_PROJECT`` / ``VERTEX_LOCATION`` / ``PIPELINE_ROOT_BUCKET`` from
``os.environ`` (propagated via ``pipeline/dags/_pod.py``), and invokes
``pipeline.workflow.compile`` with concrete argv and a writable ``--output-dir``.

Code/comments English per repo convention.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    from pipeline.workflow import compile as compile_mod

    project = (os.environ.get("GCP_PROJECT") or os.environ.get("PROJECT_ID") or "").strip()
    if not project:
        print(
            "[error] submit_train_pipeline: set GCP_PROJECT or PROJECT_ID in Composer env_var",
            file=sys.stderr,
        )
        return 1

    location = (os.environ.get("VERTEX_LOCATION") or os.environ.get("REGION") or "").strip()
    if not location:
        location = "asia-northeast1"

    bucket = (os.environ.get("PIPELINE_ROOT_BUCKET") or "").strip()
    if not bucket:
        print(
            "[error] submit_train_pipeline: PIPELINE_ROOT_BUCKET missing "
            "(Composer env_variables / _pod PROPAGATED_ENV_KEYS)",
            file=sys.stderr,
        )
        return 1

    output_dir = Path("/tmp/pipelines")
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline_root = f"gs://{bucket}/runs"
    service_account = f"sa-pipeline@{project}.iam.gserviceaccount.com"

    sys.argv = [
        "compile",
        "--target",
        "train",
        "--output-dir",
        str(output_dir),
        "--submit",
        "--project-id",
        project,
        "--location",
        location,
        "--pipeline-root",
        pipeline_root,
        "--service-account",
        service_account,
    ]
    return compile_mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
