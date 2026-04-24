"""Post-deploy checker (formerly deploy_monitor).

Usage:
  uv run python -m scripts.local.deploy_checker --api-build-id <id> --model-build-id <id>

Behavior:
1) Poll Cloud Build statuses (API + training-job image) until terminal state.
2) Confirm at least one finished training run exists.
3) Poll /readyz until rerank_enabled=true and model_path non-null.
4) Run strict component gate (same as make ops-search-components).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from typing import Any

from scripts._common import cloud_run_url, env, fail, http_json, identity_token, run


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check post-deploy gates.")
    parser.add_argument(
        "--api-build-id",
        required=False,
        default="",
        help="API Cloud Build ID to monitor (optional; omitted => auto-detect latest search-api build)",
    )
    parser.add_argument(
        "--model-build-id",
        required=False,
        default="",
        help=(
            "Model Cloud Build ID to monitor (training-job image). "
            "Optional; omitted => auto-detect latest training-job build"
        ),
    )
    parser.add_argument(
        "--poll-sec",
        type=int,
        default=10,
        help="Polling interval seconds (default: 10)",
    )
    parser.add_argument(
        "--ready-timeout-sec",
        type=int,
        default=600,
        help="Timeout for /readyz rerank check (default: 600)",
    )
    return parser.parse_args(argv)


def _resolve_latest_build_id(project_id: str, service: str) -> str:
    proc = run(
        [
            "gcloud",
            "builds",
            "list",
            f"--project={project_id}",
            "--sort-by=~create_time",
            "--limit=30",
            "--format=json",
        ],
        capture=True,
    )
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("failed to parse gcloud builds list output") from exc
    if not isinstance(rows, list):
        raise RuntimeError("gcloud builds list returned non-list payload")
    for row in rows:
        if not isinstance(row, dict):
            continue
        build_id = str(row.get("id") or "").strip()
        if not build_id:
            continue
        substitutions: dict[str, Any] = row.get("substitutions") or {}
        uri = str(substitutions.get("_URI") or "")
        images = row.get("images") or []
        uri_hit = f"/{service}:" in uri
        images_hit = any(isinstance(i, str) and f"/{service}:" in i for i in images)
        if uri_hit or images_hit:
            return build_id
    raise RuntimeError(f"no recent Cloud Build found for service={service}")


def _build_status(project_id: str, build_id: str) -> str:
    proc = run(
        [
            "gcloud",
            "builds",
            "describe",
            build_id,
            f"--project={project_id}",
            "--format=value(status)",
        ],
        capture=True,
    )
    return (proc.stdout or "").strip()


def _wait_build(project_id: str, build_id: str, poll_sec: int) -> bool:
    print(f"==> check build: id={build_id}")
    while True:
        status = _build_status(project_id, build_id)
        print(f"[build] status={status}")
        if status == "SUCCESS":
            return True
        if status in {"FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"}:
            return False
        time.sleep(max(poll_sec, 1))


def _latest_finished_training_run(project_id: str) -> dict[str, str] | None:
    query = (
        "SELECT run_id, CAST(finished_at AS STRING) AS finished_at, model_path "
        f"FROM `{project_id}.mlops.training_runs` "
        "WHERE finished_at IS NOT NULL "
        "ORDER BY finished_at DESC "
        "LIMIT 1"
    )
    proc = run(
        [
            "bq",
            "query",
            "--use_legacy_sql=false",
            f"--project_id={project_id}",
            "--format=prettyjson",
            query,
        ],
        capture=True,
    )
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    run_id = str(row.get("run_id") or "")
    finished_at = str(row.get("finished_at") or "")
    model_path = str(row.get("model_path") or "")
    if not run_id or not finished_at or not model_path:
        return None
    return {
        "run_id": run_id,
        "finished_at": finished_at,
        "model_path": model_path,
    }


def _wait_ready(*, timeout_sec: int, poll_sec: int) -> bool:
    url = cloud_run_url()
    token = identity_token()
    deadline = time.monotonic() + timeout_sec
    print(f"==> check readyz: url={url}/readyz timeout={timeout_sec}s")
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        status, body = http_json("GET", f"{url}/readyz", token=token)
        remaining = int(max(0, deadline - time.monotonic()))
        if status == 200:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                rerank_enabled = bool(parsed.get("rerank_enabled"))
                model_path = parsed.get("model_path")
                if rerank_enabled and bool(model_path):
                    print(
                        "[readyz] READY "
                        f"(attempt={attempt}, remaining={remaining}s, "
                        f"rerank_enabled={rerank_enabled}, model_path={model_path})"
                    )
                    return True
                print(
                    "[readyz] WAITING "
                    f"(attempt={attempt}, remaining={remaining}s, "
                    f"search_enabled={parsed.get('search_enabled')}, "
                    f"rerank_enabled={parsed.get('rerank_enabled')}, "
                    f"model_path={parsed.get('model_path')}) "
                    "- startup/model warm-up in progress"
                )
            else:
                print(
                    f"[readyz] WAITING (attempt={attempt}, remaining={remaining}s) "
                    "- response JSON shape is unexpected"
                )
        else:
            print(
                f"[readyz] WAITING (attempt={attempt}, remaining={remaining}s, http={status}) "
                "- service still converging"
            )
        time.sleep(max(poll_sec, 1))
    return False


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_id = env("PROJECT_ID")
    api_service = env("API_SERVICE")
    training_job = env("TRAINING_JOB")

    api_build_id = args.api_build_id.strip()
    if not api_build_id:
        try:
            api_build_id = _resolve_latest_build_id(project_id, api_service)
        except Exception as exc:
            return fail(f"deploy-checker config error: failed to auto-resolve api build id: {exc}")
        print(f"==> auto-detected api build id: {api_build_id} (service={api_service})")

    model_build_id = args.model_build_id.strip()
    if not model_build_id:
        try:
            model_build_id = _resolve_latest_build_id(project_id, training_job)
        except Exception as exc:
            return fail(
                f"deploy-checker config error: failed to auto-resolve model build id: {exc}"
            )
        print(
            f"==> auto-detected model build id: {model_build_id} "
            f"(training job image={training_job})"
        )

    if not _wait_build(project_id, api_build_id, args.poll_sec):
        return fail("deploy-checker failed: API Cloud Build did not succeed")
    if not _wait_build(project_id, model_build_id, args.poll_sec):
        return fail("deploy-checker failed: model Cloud Build did not succeed")

    latest_run = _latest_finished_training_run(project_id)
    if latest_run is None:
        return fail("deploy-checker failed: no finished training run found in mlops.training_runs")
    print(
        "==> latest finished training run: "
        f"run_id={latest_run['run_id']} finished_at={latest_run['finished_at']} "
        f"model_path={latest_run['model_path']}"
    )

    if not _wait_ready(timeout_sec=args.ready_timeout_sec, poll_sec=args.poll_sec):
        return fail(
            "deploy-checker failed: /readyz did not reach rerank_enabled=true with model_path set"
        )

    print("==> run component gate")
    proc = subprocess.run(
        ["uv", "run", "python", "-m", "scripts.local.search_component_check"],
        check=False,
    )
    if proc.returncode != 0:
        return fail("deploy-checker failed: component gate did not pass")

    print(
        "==> deploy-checker passed: "
        "api-build success + model-build success + training-run present + "
        "readyz rerank + component gate"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
