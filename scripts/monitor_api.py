#!/usr/bin/env python3
"""API健全性監視: /health チェック + Discord通知"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_ID = "mlops-dev-a"
REGION = "asia-northeast1"
SERVICE_NAME = "ml-api"

COLOR_SUCCESS = 3066993   # 緑
COLOR_FAILURE = 15158332  # 赤


def load_env() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def get_api_url() -> str | None:
    result = subprocess.run(
        [
            "gcloud", "run", "services", "describe", SERVICE_NAME,
            f"--region={REGION}",
            f"--project={PROJECT_ID}",
            "--format=value(status.url)",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"gcloud エラー: {result.stderr}", file=sys.stderr)
        return None
    return result.stdout.strip()


def check_health(api_url: str) -> tuple[str, str]:
    url = f"{api_url}/health"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        status = data.get("status", "unknown")
        model_path = data.get("model_path", "不明")

        if status == "ok":
            return "SUCCESS", f"API正常: モデル={model_path}"
        else:
            return "DEGRADED", f"API劣化状態: status={status}, モデル={model_path}"

    except Exception as e:
        return "FAILED", f"APIヘルスチェック失敗: {e}"


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
                    {"name": "Service", "value": f"`{SERVICE_NAME}`", "inline": True},
                    {"name": "ステータス", "value": status, "inline": True},
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
    load_env()

    api_url = get_api_url()
    if not api_url:
        notify_discord("FAILED", "API URL取得失敗")
        return

    status, message = check_health(api_url)
    print(f"[{status}] {message}")

    # 正常時は通知しない（異常時のみ）
    if status != "SUCCESS":
        notify_discord(status, message)


if __name__ == "__main__":
    main()
