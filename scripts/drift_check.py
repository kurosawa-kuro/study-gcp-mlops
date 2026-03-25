#!/usr/bin/env python3
"""モデルドリフト検知: 直近のRMSEが閾値を超えていたらDiscord通知"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_ID = "mlops-dev-a"
DATASET = "mlops"
RMSE_THRESHOLD = float(os.environ.get("RMSE_THRESHOLD", "0.6"))

COLOR_SUCCESS = 3066993   # 緑
COLOR_WARNING = 16776960  # 黄
COLOR_FAILURE = 15158332  # 赤


def load_env() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def get_latest_metrics() -> dict | None:
    """BigQueryから直近のメトリクスを取得。"""
    query = f"""
    SELECT run_id, rmse, mae, model_path, timestamp
    FROM `{PROJECT_ID}.{DATASET}.metrics`
    ORDER BY timestamp DESC
    LIMIT 1
    """
    result = subprocess.run(
        ["bq", "query", "--use_legacy_sql=false", "--format=json", query],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"bq エラー: {result.stderr}", file=sys.stderr)
        return None

    rows = json.loads(result.stdout)
    return rows[0] if rows else None


def get_average_rmse(n: int = 5) -> float | None:
    """直近N件のRMSE平均を取得。"""
    query = f"""
    SELECT AVG(rmse) as avg_rmse
    FROM (
        SELECT rmse FROM `{PROJECT_ID}.{DATASET}.metrics`
        ORDER BY timestamp DESC
        LIMIT {n}
    )
    """
    result = subprocess.run(
        ["bq", "query", "--use_legacy_sql=false", "--format=json", query],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None

    rows = json.loads(result.stdout)
    if rows and rows[0].get("avg_rmse"):
        return float(rows[0]["avg_rmse"])
    return None


def notify_discord(status: str, message: str, fields: list[dict]) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL が未設定のため通知スキップ")
        return

    color_map = {"SUCCESS": COLOR_SUCCESS, "WARNING": COLOR_WARNING, "FAILED": COLOR_FAILURE}
    payload = {
        "embeds": [
            {
                "title": message,
                "color": color_map.get(status, COLOR_FAILURE),
                "fields": fields,
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

    latest = get_latest_metrics()
    if not latest:
        print("[ERROR] メトリクス取得失敗")
        notify_discord("FAILED", "ドリフト検知: メトリクス取得失敗", [])
        return

    rmse = float(latest["rmse"])
    avg_rmse = get_average_rmse()

    fields = [
        {"name": "最新RMSE", "value": f"{rmse:.4f}", "inline": True},
        {"name": "閾値", "value": f"{RMSE_THRESHOLD:.4f}", "inline": True},
    ]
    if avg_rmse:
        fields.append({"name": "直近5件平均RMSE", "value": f"{avg_rmse:.4f}", "inline": True})

    if rmse > RMSE_THRESHOLD:
        status = "WARNING"
        message = f"モデルドリフト検知: RMSE={rmse:.4f} > 閾値{RMSE_THRESHOLD:.4f}"
        print(f"[WARNING] {message}")
        notify_discord(status, message, fields)
    else:
        status = "SUCCESS"
        message = f"モデル正常: RMSE={rmse:.4f}"
        print(f"[OK] {message}")
        # 正常時は通知しない


if __name__ == "__main__":
    main()
