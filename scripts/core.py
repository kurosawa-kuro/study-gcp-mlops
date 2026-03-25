"""scripts共通ユーティリティ"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# === プロジェクト定数 ===
PROJECT_ID = "mlops-dev-a"
REGION = "asia-northeast1"
DATASET = "mlops"

# === Discord通知カラー ===
COLOR_SUCCESS = 3066993   # 緑
COLOR_WARNING = 16776960  # 黄
COLOR_FAILURE = 15158332  # 赤

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    """プロジェクトルートの.envファイルを読み込む。"""
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def run(cmd: str, allow_fail: bool = False) -> None:
    """シェルコマンドを実行する。失敗時はsys.exit。"""
    print(f"\n==> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT)
    if result.returncode != 0 and not allow_fail:
        print(f"エラー: '{cmd}' が失敗しました (code={result.returncode})")
        sys.exit(result.returncode)


def notify_discord(status: str, message: str, fields: list[dict] | None = None) -> None:
    """Discord Webhookで通知を送信する。"""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL が未設定のため通知スキップ")
        return

    color_map = {"SUCCESS": COLOR_SUCCESS, "WARNING": COLOR_WARNING, "FAILED": COLOR_FAILURE}
    embed = {
        "title": message,
        "color": color_map.get(status, COLOR_FAILURE),
    }
    if fields:
        embed["fields"] = fields

    payload = {"embeds": [embed]}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)
    print(f"Discord通知送信: {status}")
