"""Run ID の生成."""

import uuid
from datetime import datetime


def generate_run_id() -> str:
    """一意な run ID を生成する。形式: YYYYMMDD_HHMMSS_xxxxxx"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"{ts}_{short_uuid}"
