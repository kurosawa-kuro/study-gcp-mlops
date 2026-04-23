"""Shared helpers for scripts/*.py and scripts/ops/*.py.

Stdlib-only by design (per scripts/README.md). The functions wrap the most
common shell idioms (gcloud subprocess calls, IAM-gated HTTP requests,
env-var defaults) so individual scripts stay short and focused on intent.

DEFAULTS are loaded at import time from `env/config/setting.yaml` so the
project-wide constants (project_id / region / api_service / training_job /
artifact_repo / vertex_location / pipeline_root_bucket / pipeline_template_gcs_path)
live in exactly one place. The YAML parser is a deliberately minimal
hand-rolled flat-key:value reader to keep the stdlib-only promise
(no PyYAML dependency).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "env" / "config" / "setting.yaml"


def _load_settings() -> dict[str, str]:
    """Parse the flat key:value subset of env/config/setting.yaml.

    Supported syntax: top-level `key: value` lines, `#` comments, blank lines.
    Values may be quoted with `"` or `'`. Anything else (nesting, anchors,
    multiline strings) is intentionally rejected to keep this parser tiny.
    """
    settings: dict[str, str] = {}
    if not _SETTINGS_PATH.exists():
        return settings
    for raw in _SETTINGS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        # Skip YAML list markers (lines like `- foo`) and block-style list keys
        # (e.g. `admin_user_emails:` with an empty value followed by `- foo`).
        if key.startswith("-"):
            continue
        if value:
            settings[key.upper()] = value
    return settings


DEFAULTS = _load_settings()


def env(name: str, default: str | None = None) -> str:
    """Read an env var with a project-wide default fallback."""
    fallback = default if default is not None else DEFAULTS.get(name, "")
    return os.environ.get(name, fallback)


def run(
    cmd: list[str], *, capture: bool = False, check: bool = True, timeout: int | None = None
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper around subprocess.run. `capture=True` returns stdout in `.stdout`."""
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        timeout=timeout,
    )


def gcloud(*args: str, capture: bool = False) -> str:
    """Invoke gcloud with the supplied args. Returns stripped stdout when capture=True."""
    proc = run(["gcloud", *args], capture=capture)
    return proc.stdout.strip() if capture and proc.stdout else ""


def cloud_run_url(service: str | None = None) -> str:
    """Resolve a Cloud Run Service URL via `gcloud run services describe`.

    Phase 6 note: Meilisearch still runs on Cloud Run, so this helper remains
    valid. For the search-api URL (now on GKE Gateway), use `api_external_url()`.
    Calling without an explicit service is rejected to prevent accidental
    Phase-5-style usage.
    """
    if service is None:
        raise RuntimeError(
            "cloud_run_url() requires an explicit service name in Phase 6. "
            "Use api_external_url() for search-api."
        )
    return gcloud(
        "run",
        "services",
        "describe",
        service,
        f"--project={env('PROJECT_ID')}",
        f"--region={env('REGION')}",
        "--format=value(status.url)",
        capture=True,
    )


def api_external_url() -> str:
    """Resolve the search-api GKE Gateway external URL via kubectl."""
    url = run(
        [
            "kubectl",
            "get",
            "gateway",
            "search-api-gateway",
            "--namespace=search",
            "-o",
            "jsonpath={.status.addresses[0].value}",
        ],
        capture=True,
        check=False,
    ).stdout.strip()
    if not url:
        raise RuntimeError(
            "search-api-gateway has no address yet. "
            "Ensure `kubectl apply -k infra/manifests/` has been run and the Gateway is provisioned."
        )
    return url if url.startswith("http") else f"https://{url}"


def identity_token() -> str:
    """Mint an OIDC token for IAM-gated GKE Gateway / Cloud Run calls."""
    return gcloud("auth", "print-identity-token", capture=True)


def http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    timeout: int = 30,
) -> tuple[int, str]:
    """POST/GET JSON with optional Bearer token. Returns (status_code, body_text)."""
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body


def fail(msg: str, code: int = 1) -> int:
    """Print to stderr and return an exit code (use as `return fail("...")`)."""
    print(msg, file=sys.stderr)
    return code


def print_pretty(body: str) -> None:
    """Best-effort pretty-print of a JSON body (falls back to raw)."""
    try:
        print(json.dumps(json.loads(body), ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(body)


def submit_cloud_build_async(
    *, project_id: str, config: str, substitutions: str, timeout: int | None = None
) -> str:
    """Submit Cloud Build asynchronously and return build id."""
    proc = run(
        [
            "gcloud",
            "builds",
            "submit",
            f"--project={project_id}",
            f"--config={config}",
            f"--substitutions={substitutions}",
            "--async",
            "--format=value(id)",
            ".",
        ],
        capture=True,
        timeout=timeout,
    )
    build_id = (proc.stdout or "").strip()
    if not build_id:
        raise RuntimeError("cloud build submission returned empty build id")
    return build_id


def wait_cloud_build(
    *,
    project_id: str,
    build_id: str,
    timeout_sec: int,
    poll_sec: int = 10,
) -> None:
    """Poll Cloud Build status and fail fast on timeout/failure."""

    def _print_build_diagnostics() -> None:
        try:
            summary = gcloud(
                "builds",
                "describe",
                build_id,
                f"--project={project_id}",
                "--format=value(logUrl,status,createTime,startTime,finishTime)",
                capture=True,
            )
            if summary:
                print(f"[cloud-build] summary: {summary}", file=sys.stderr)
        except Exception as exc:  # pragma: no cover
            print(f"[cloud-build] failed to fetch describe summary: {exc}", file=sys.stderr)

    deadline = time.monotonic() + timeout_sec
    while True:
        status = gcloud(
            "builds",
            "describe",
            build_id,
            f"--project={project_id}",
            "--format=value(status)",
            capture=True,
        )
        if status == "SUCCESS":
            return
        if status in {"FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"}:
            _print_build_diagnostics()
            raise RuntimeError(f"cloud build {build_id} failed with status={status}")
        if time.monotonic() >= deadline:
            run(
                ["gcloud", "builds", "cancel", build_id, f"--project={project_id}"],
                check=False,
            )
            _print_build_diagnostics()
            raise RuntimeError(
                f"cloud build {build_id} exceeded timeout ({timeout_sec}s) and was cancelled"
            )
        time.sleep(poll_sec)
