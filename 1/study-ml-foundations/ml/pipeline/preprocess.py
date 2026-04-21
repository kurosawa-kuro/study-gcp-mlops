"""前処理 — 欠損値処理・外れ値キャップ・対数変換."""

import numpy as np
import pandas as pd

from share import FEATURE_COLS, TARGET_COL, get_logger

logger = get_logger(__name__)

# 外れ値キャップ対象（パーセンタイル上限）
CAP_COLS = ["Population", "AveOccup", "AveRooms", "AveBedrms"]
CAP_UPPER_PERCENTILE = 99

# 対数変換対象（右に裾が長い分布）
LOG_COLS = ["Population", "AveOccup"]


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """前処理を適用して DataFrame を返す."""
    df = df.copy()
    df = _handle_missing(df)
    df = _cap_outliers(df)
    df = _log_transform(df)
    return df


def _handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    """欠損値を中央値で補完する."""
    cols = [c for c in FEATURE_COLS + [TARGET_COL] if c in df.columns]
    missing = df[cols].isnull().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        logger.warning("Missing values found:\n%s", missing.to_string())
        df[cols] = df[cols].fillna(df[cols].median())
    return df


def _cap_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """指定カラムの外れ値をパーセンタイルでキャップする."""
    for col in CAP_COLS:
        if col not in df.columns:
            continue
        upper = np.percentile(df[col], CAP_UPPER_PERCENTILE)
        n_capped = (df[col] > upper).sum()
        if n_capped > 0:
            df[col] = df[col].clip(upper=upper)
            logger.info("Capped %s: %d rows (upper=%.2f)", col, n_capped, upper)
    return df


def _log_transform(df: pd.DataFrame) -> pd.DataFrame:
    """指定カラムに log1p 変換を適用する."""
    for col in LOG_COLS:
        if col not in df.columns:
            continue
        df[col] = np.log1p(df[col])
        logger.info("Log-transformed %s", col)
    return df


def preprocess_input(values: dict) -> dict:
    """推論用の単一レコードに対数変換を適用する（API 向け）."""
    out = dict(values)
    for col in LOG_COLS:
        if col in out:
            out[col] = float(np.log1p(out[col]))
    return out
