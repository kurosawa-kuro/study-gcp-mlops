"""特徴量エンジニアリング — 既存の特徴量から新しい特徴量を生成."""

import pandas as pd

from share import get_logger

logger = get_logger(__name__)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """バッチ用: DataFrame に特徴量を追加して返す."""
    df = df.copy()
    df["BedroomRatio"] = df["AveBedrms"] / df["AveRooms"]
    df["RoomsPerPerson"] = df["AveRooms"] / df["AveOccup"]
    logger.info("Engineered 2 features: BedroomRatio, RoomsPerPerson")
    return df


def engineer_features_input(values: dict) -> dict:
    """推論用: 単一レコードに特徴量を追加して返す（API 向け）."""
    out = dict(values)
    out["BedroomRatio"] = out["AveBedrms"] / out["AveRooms"]
    out["RoomsPerPerson"] = out["AveRooms"] / out["AveOccup"]
    return out
