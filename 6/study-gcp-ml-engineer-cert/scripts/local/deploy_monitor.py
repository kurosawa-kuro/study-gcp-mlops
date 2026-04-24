"""Real-time monitor for long-running deploy / verification commands (Phase 6 generic).

Usage (deploy-all, 既定):
  make ops-deploy-monitor
  uv run python -m scripts.local.deploy_monitor

Usage (任意コマンドをラップ):
  make ops-monitor CMD="make deploy-api-local"
  make ops-monitor LABEL=bqml CMD="make bqml-train-popularity"
  uv run python -m scripts.local.deploy_monitor --label bqml -- make bqml-train-popularity

Behavior:
1) Starts the target command as a child process (unbuffered output).
2) Streams logs in real time and extracts current step context (`step N/M: ...`).
3) During Cloud Build wait, periodically prints build status/log URL.
4) Detects long silent periods and reports where execution is stuck.
5) On failure, prints likely root cause with step/build context.

Phase 6 では deploy-all 以外の細かい target (make deploy-api-local / make
tf-apply 相当 / make seed-test / make bqml-train-popularity 等) にも一律に
monitor を被せてトライアンドエラーできるよう、汎用 CLI に拡張している。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from scripts._common import env, fail, run

_DEFAULT_CMD: list[str] = ["uv", "run", "python", "-u", "-m", "scripts.local.setup.deploy_all"]
_DEFAULT_LABEL = "deploy-all"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor a long-running deploy / verification command in real time."
    )
    parser.add_argument(
        "--poll-sec",
        type=int,
        default=8,
        help="Polling interval for progress heartbeat (default: 8)",
    )
    parser.add_argument(
        "--stall-warn-sec",
        type=int,
        default=120,
        help="Warn when no new log line is seen for this many seconds (default: 120)",
    )
    parser.add_argument(
        "--quiet-steps",
        action="store_true",
        help="Do not print every raw line; print only heartbeat/summary logs",
    )
    parser.add_argument(
        "--label",
        default=None,
        help=(
            "Label used in monitor prints (default: 'deploy-all' when running "
            "the default command, otherwise 'cmd')."
        ),
    )
    parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help=(
            "Command to monitor. Pass after `--`, e.g. "
            "`uv run python -m scripts.local.deploy_monitor -- make deploy-api-local`. "
            "Omit to default to deploy-all."
        ),
    )
    return parser.parse_args(argv)


def _build_describe(project_id: str, build_id: str) -> tuple[str, str]:
    proc = run(
        [
            "gcloud",
            "builds",
            "describe",
            build_id,
            f"--project={project_id}",
            "--format=json",
        ],
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return "", ""
    status = str(payload.get("status") or "")
    log_url = str(payload.get("logUrl") or "")
    return status, log_url


# `<label> step N/M: description` をキャプチャ (deploy-all / 任意 label どちらも対応)。
# 例: "deploy-all step 3/7: recover WIF" / "verify step 2/5: ops-search-components"
_STEP_RE = re.compile(r"\bstep\s+(\d+)/(\d+):\s+(.+)$")
_BUILD_WAIT_RE = re.compile(r"Cloud Build wait id=([a-z0-9-]+)\s+timeout=(\d+)s")
# gcloud run deploy / gcloud builds submit 途中の build-id 検知 (deploy-api-local 単体でも拾えるよう追加)
_GCLOUD_BUILD_ID_RE = re.compile(r"builds/([a-z0-9-]{20,})")


@dataclass
class MonitorState:
    current_step_no: int = 0
    current_step_total: int = 0
    current_step_label: str = "not-started"
    current_build_id: str = ""
    current_build_timeout_sec: int = 0
    current_build_started_at: float = 0.0
    last_line_at: float = 0.0
    last_line: str = ""


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _maybe_parse_step(line: str, state: MonitorState) -> None:
    m = _STEP_RE.search(line)
    if not m:
        return
    state.current_step_no = int(m.group(1))
    state.current_step_total = int(m.group(2))
    state.current_step_label = m.group(3).strip()
    state.current_build_id = ""
    state.current_build_timeout_sec = 0
    state.current_build_started_at = 0.0
    print(
        f"[monitor] step-enter step={state.current_step_no}/{state.current_step_total} "
        f"label={state.current_step_label}"
    )


def _maybe_parse_build_wait(line: str, state: MonitorState, now_ts: float) -> None:
    m = _BUILD_WAIT_RE.search(line)
    if m:
        state.current_build_id = m.group(1)
        state.current_build_timeout_sec = int(m.group(2))
        state.current_build_started_at = now_ts
        print(
            f"[monitor] build-wait-start build_id={state.current_build_id} "
            f"timeout_sec={state.current_build_timeout_sec} step={state.current_step_no}"
        )
        return
    # `gcloud builds submit` / `gcloud run deploy` は標準出力に build id を含む URL を出す。
    # 汎用 monitor では timeout がわからないので 0 のまま build_id だけ拾って heartbeat で
    # status を追えるようにする (第二候補: timeout 検知のための別系統を確保する目的)。
    if state.current_build_id:
        return
    m2 = _GCLOUD_BUILD_ID_RE.search(line)
    if not m2:
        return
    state.current_build_id = m2.group(1)
    state.current_build_timeout_sec = 0
    state.current_build_started_at = now_ts
    print(
        f"[monitor] build-id-detected build_id={state.current_build_id} "
        f"step={state.current_step_no} (timeout unknown — gcloud inline build)"
    )


def _print_heartbeat(
    state: MonitorState, project_id: str, now_ts: float, stall_warn_sec: int
) -> None:
    idle_sec = int(max(0, now_ts - state.last_line_at))
    base = (
        f"[monitor] heartbeat t={_now_utc()} step={state.current_step_no}/{state.current_step_total} "
        f"label={state.current_step_label} idle_sec={idle_sec}"
    )

    if state.current_build_id:
        status, log_url = _build_describe(project_id, state.current_build_id)
        elapsed = int(max(0, now_ts - state.current_build_started_at))
        timeout_sec = state.current_build_timeout_sec
        remaining = max(0, timeout_sec - elapsed) if timeout_sec else -1
        print(
            f"{base} build_id={state.current_build_id} build_status={status} "
            f"build_elapsed_sec={elapsed} build_remaining_sec={remaining}"
        )
        if log_url:
            print(f"[monitor] build-log-url {log_url}")
    else:
        print(base)

    if idle_sec >= stall_warn_sec:
        print(
            "[monitor] stall-warning "
            f"no-new-log-for={idle_sec}s current_step={state.current_step_no} "
            f"last_line={state.last_line}"
        )


def _resolve_cmd(raw: list[str]) -> tuple[list[str], bool]:
    """Resolve user-provided command (after argparse REMAINDER).

    - `[]` → default deploy-all command, is_default=True.
    - leading `--` is stripped (argparse.REMAINDER quirk with explicit separator).
    - Single-token that contains whitespace is re-split via shlex so that
      `make ops-monitor CMD="make deploy-api-local"` works without array quoting.
    """
    if not raw:
        return list(_DEFAULT_CMD), True
    tokens = list(raw)
    if tokens and tokens[0] == "--":
        tokens = tokens[1:]
    if len(tokens) == 1 and any(ch.isspace() for ch in tokens[0]):
        tokens = shlex.split(tokens[0])
    if not tokens:
        return list(_DEFAULT_CMD), True
    return tokens, False


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_id = env("PROJECT_ID")
    state = MonitorState()
    now = time.monotonic()
    state.last_line_at = now
    state.current_step_label = "launching"

    cmd, is_default = _resolve_cmd(args.cmd or [])
    label = args.label or (_DEFAULT_LABEL if is_default else "cmd")

    child_env = dict(os.environ)
    child_env["PYTHONUNBUFFERED"] = "1"
    print(f"[monitor] start label={label} command={' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=child_env,
    )

    assert proc.stdout is not None
    next_heartbeat = time.monotonic() + max(1, args.poll_sec)
    poll_interval = min(max(1, args.poll_sec), 2)
    while True:
        now_ts = time.monotonic()
        ready, _, _ = select.select([proc.stdout], [], [], poll_interval)
        if ready:
            line = proc.stdout.readline()
            if line:
                stripped = line.rstrip("\n")
                state.last_line = stripped
                state.last_line_at = now_ts
                _maybe_parse_step(stripped, state)
                _maybe_parse_build_wait(stripped, state, now_ts)
                if not args.quiet_steps:
                    print(stripped)
            elif proc.poll() is not None:
                break
        elif proc.poll() is not None:
            break

        if now_ts >= next_heartbeat:
            _print_heartbeat(state, project_id, now_ts, args.stall_warn_sec)
            next_heartbeat = now_ts + max(1, args.poll_sec)

    rc = proc.wait()
    if rc == 0:
        print(
            f"[monitor] {label} succeeded "
            f"final_step={state.current_step_no}/{state.current_step_total} "
            f"label={state.current_step_label}"
        )
        return 0

    failure_reason = f"{label} returned non-zero (rc={rc})"
    if state.current_build_id:
        status, log_url = _build_describe(project_id, state.current_build_id)
        if status in {"WORKING", "QUEUED"}:
            failure_reason = (
                f"{label} failed during cloud-build wait "
                f"(build_id={state.current_build_id}, status={status}, step={state.current_step_no})"
            )
        else:
            failure_reason = (
                f"{label} failed after cloud-build completed "
                f"(build_id={state.current_build_id}, status={status}, step={state.current_step_no}, "
                f"last_line={state.last_line})"
            )
        if log_url:
            print(f"[monitor] failure-build-log-url {log_url}")
        if status == "TIMEOUT":
            failure_reason += " timeout detected in Cloud Build"
    elif state.current_step_no > 0:
        failure_reason = (
            f"{label} failed at step {state.current_step_no}/{state.current_step_total} "
            f"({state.current_step_label})"
        )
    else:
        # 第二候補: step も build id もない → 直近の非空出力行をヒントとして残す。
        if state.last_line:
            failure_reason += f" last_line={state.last_line!r}"
    return fail(f"[monitor] {failure_reason}")


if __name__ == "__main__":
    raise SystemExit(main())
