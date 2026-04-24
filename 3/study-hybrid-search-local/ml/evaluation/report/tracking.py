"""Local experiment tracking helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNS_DIR = _REPO_ROOT / "runs"


def log_metrics_local(run_id: str, metrics: dict[str, Any]) -> None:
    """Write metrics to runs/{run_id}/metrics.json for local tracking."""
    run_dir = _RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
