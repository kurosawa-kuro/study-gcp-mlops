#!/usr/bin/env python3
"""API健全性監視: /health チェック + Discord通知"""

import json
import subprocess
import urllib.request

from core import PROJECT_ID, REGION, load_env, notify_discord, setup_logging

logger = setup_logging("monitor-api")

SERVICE_NAME = "ml-api"


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
        logger.error(f"gcloud エラー: {result.stderr}")
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


def main() -> None:
    load_env()

    api_url = get_api_url()
    if not api_url:
        notify_discord("FAILED", "API URL取得失敗", [
            {"name": "Service", "value": f"`{SERVICE_NAME}`", "inline": True},
        ])
        return

    status, message = check_health(api_url)
    logger.info(f"[{status}] {message}")

    if status != "SUCCESS":
        notify_discord(status, message, [
            {"name": "Service", "value": f"`{SERVICE_NAME}`", "inline": True},
            {"name": "ステータス", "value": status, "inline": True},
        ])


if __name__ == "__main__":
    main()
