"""評価指標の算出・保存（numpy 自前実装, scikit-learn 不要）."""

import json
from pathlib import Path

import numpy as np

from common import get_logger

logger = get_logger(__name__)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0.0:
        return 0.0 if ss_res == 0.0 else float("nan")
    return 1 - ss_res / ss_tot


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """RMSE と R² を算出して dict で返す."""
    return {
        "rmse": round(rmse(y_true, y_pred), 4),
        "r2": round(r2_score(y_true, y_pred), 4),
    }


def save_metrics(metrics: dict, path: str) -> None:
    """metrics を JSON ファイルに保存する."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2))
    logger.info("Metrics saved to %s", out)
