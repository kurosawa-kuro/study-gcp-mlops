"""Monitor deploy progress and run post-deploy gates.

Usage:
  uv run python -m scripts.local.deploy_monitor --build-id <cloud-build-id>

Behavior:
1) Poll Cloud Build status until terminal state.
2) If build succeeded, poll /readyz until rerank_enabled=true and model_path non-null.
3) Run strict component gate (same as make ops-search-components).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from typing import Any

from scripts._common import cloud_run_url, env, fail, http_json, identity_token, run


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor deploy and validate final gates.")
    parser.add_argument(
        "--build-id",
        required=False,
        default="",
        help="Cloud Build ID to monitor (optional; omitted => auto-detect latest search-api build)",
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
    print(f"==> monitor build: id={build_id}")
    while True:
        status = _build_status(project_id, build_id)
        print(f"[build] status={status}")
        if status == "SUCCESS":
            return True
        if status in {"FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"}:
            return False
        time.sleep(max(poll_sec, 1))


def _wait_ready(*, timeout_sec: int, poll_sec: int) -> bool:
    url = cloud_run_url()
    token = identity_token()
    deadline = time.monotonic() + timeout_sec
    print(f"==> monitor readyz: url={url}/readyz timeout={timeout_sec}s")
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
    service = env("API_SERVICE")
    build_id = args.build_id.strip()
    if not build_id:
        try:
            build_id = _resolve_latest_build_id(project_id, service)
        except Exception as exc:
            return fail(f"deploy-monitor config error: failed to auto-resolve build id: {exc}")
        print(f"==> auto-detected build id: {build_id} (service={service})")

    if not _wait_build(project_id, build_id, args.poll_sec):
        return fail("deploy-monitor failed: Cloud Build did not succeed")

    if not _wait_ready(timeout_sec=args.ready_timeout_sec, poll_sec=args.poll_sec):
        return fail(
            "deploy-monitor failed: /readyz did not reach rerank_enabled=true with model_path set"
        )

    print("==> run component gate")
    proc = subprocess.run(
        ["uv", "run", "python", "-m", "scripts.local.search_component_check"],
        check=False,
    )
    if proc.returncode != 0:
        return fail("deploy-monitor failed: component gate did not pass")

    print("==> deploy-monitor passed: build success + readyz rerank + component gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
