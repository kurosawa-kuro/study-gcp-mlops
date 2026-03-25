#!/usr/bin/env python3
"""Cloud Run Job 監視 + Discord通知"""

import json
import subprocess

from core import PROJECT_ID, REGION, load_env, notify_discord, setup_logging

logger = setup_logging("monitor-batch")

JOB_NAME = "ml-batch"
CONSOLE_URL = f"https://console.cloud.google.com/run/jobs/details/{REGION}/{JOB_NAME}?project={PROJECT_ID}"


def get_latest_execution() -> dict | None:
    result = subprocess.run(
        [
            "gcloud", "run", "jobs", "executions", "list",
            f"--job={JOB_NAME}",
            f"--region={REGION}",
            f"--project={PROJECT_ID}",
            "--limit=1",
            "--format=json",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error(f"gcloud エラー: {result.stderr}")
        return None

    executions = json.loads(result.stdout)
    return executions[0] if executions else None


def check_status(execution: dict) -> tuple[str, str]:
    conditions = execution.get("status", {}).get("conditions", [])
    for cond in conditions:
        if cond.get("type") == "Completed":
            if cond.get("status") == "True":
                return "SUCCESS", "Cloud Run Job 実行成功"
            else:
                reason = cond.get("message", "不明なエラー")
                return "FAILED", f"Cloud Run Job 実行失敗: {reason}"
    return "UNKNOWN", "Cloud Run Job ステータス不明"


def main() -> None:
    load_env()

    execution = get_latest_execution()
    if execution is None:
        notify_discord("FAILED", "Cloud Run Job 実行履歴なし", [
            {"name": "Job", "value": f"`{JOB_NAME}`", "inline": True},
        ])
        return

    status, message = check_status(execution)
    logger.info(f"[{status}] {message}")
    notify_discord(status, message, [
        {"name": "Job", "value": f"`{JOB_NAME}`", "inline": True},
        {"name": "ステータス", "value": status, "inline": True},
        {"name": "コンソール", "value": f"[GCPで確認]({CONSOLE_URL})"},
    ])


if __name__ == "__main__":
    main()
