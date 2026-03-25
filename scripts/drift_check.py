#!/usr/bin/env python3
"""モデルドリフト検知: 直近のRMSEが閾値を超えていたらDiscord通知"""

import json
import os
import subprocess

from core import DATASET, PROJECT_ID, load_env, notify_discord, setup_logging

logger = setup_logging("drift-check")

RMSE_THRESHOLD = float(os.environ.get("RMSE_THRESHOLD", "0.6"))


def get_latest_metrics() -> dict | None:
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
        logger.error(f"bq エラー: {result.stderr}")
        return None

    rows = json.loads(result.stdout)
    return rows[0] if rows else None


def get_average_rmse(n: int = 5) -> float | None:
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


def main() -> None:
    load_env()

    latest = get_latest_metrics()
    if not latest:
        logger.error("メトリクス取得失敗")
        notify_discord("FAILED", "ドリフト検知: メトリクス取得失敗")
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
        message = f"モデルドリフト検知: RMSE={rmse:.4f} > 閾値{RMSE_THRESHOLD:.4f}"
        logger.warning(message)
        notify_discord("WARNING", message, fields)
    else:
        logger.info(f"モデル正常: RMSE={rmse:.4f}")


if __name__ == "__main__":
    main()
