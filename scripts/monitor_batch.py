#!/usr/bin/env python3
"""Cloud Run Job 監視 + Discord通知"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_ID = "mlops-dev-a"
REGION = "asia-northeast1"
JOB_NAME = "ml-batch"

COLOR_SUCCESS = 3066993   # 0x2ECC71 緑
COLOR_FAILURE = 15158332  # 0xE74C3C 赤
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
        print(f"gcloud エラー: {result.stderr}", file=sys.stderr)
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


def notify_discord(status: str, message: str) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL が未設定のため通知スキップ")
        return

    color = COLOR_SUCCESS if status == "SUCCESS" else COLOR_FAILURE
    payload = {
        "embeds": [
            {
                "title": message,
                "color": color,
                "fields": [
                    {"name": "Job", "value": f"`{JOB_NAME}`", "inline": True},
                    {"name": "ステータス", "value": status, "inline": True},
                    {"name": "コンソール", "value": f"[GCPで確認]({CONSOLE_URL})"},
                ],
            }
        ]
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)
    print(f"Discord通知送信: {status}")


def main() -> None:
    # .env ファイルがあれば読み込み
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

    execution = get_latest_execution()
    if execution is None:
        notify_discord("FAILED", "Cloud Run Job 実行履歴なし")
        return

    status, message = check_status(execution)
    print(f"[{status}] {message}")
    notify_discord(status, message)


if __name__ == "__main__":
    main()
