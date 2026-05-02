"""Phase 7 Composer DAG 横断 helper.

Composer 環境の Airflow worker が DAG を import するときに走る軽量 helper。
SDK / 重い依存はここで import せず、各 DAG 側 (or Operator 内 callable) に
閉じる。これは scheduler reparse 時のコストを抑えるための設計判断。

env 経由の値解決は `os.environ.get` で素直に行う。Airflow Variable は使わない
(metadata DB 依存を避け、Terraform output → env_variables で再注入可能に
保つ。詳細は infra/terraform/modules/composer/main.tf のコメント参照)。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

DEFAULT_TIMEZONE = "Asia/Tokyo"


def env(name: str, default: str = "") -> str:
    """Composer 環境変数を読む。空文字 → default。"""
    value = os.environ.get(name, "").strip()
    return value or default


def project_id() -> str:
    pid = env("PROJECT_ID")
    if not pid:
        raise RuntimeError("PROJECT_ID env is empty (set via Composer env_variables)")
    return pid


def region() -> str:
    return env("REGION", "asia-northeast1")


def vertex_location() -> str:
    return env("VERTEX_LOCATION", "asia-northeast1")


def fixed_start_date() -> datetime:
    """全 DAG 共通の固定 start_date。

    Airflow scheduler は `start_date` を base に schedule を回すため、
    日次 DAG が re-deploy のたびに backfill を起こさないよう **遠い過去の
    固定値** を使う (`catchup=False` も合わせる)。
    """
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


DEFAULT_DAG_ARGS: dict[str, object] = {
    "owner": "phase7-canonical",
    "retries": 0,
    "depends_on_past": False,
}
