"""sklearn California Housing データをローカル保存し PostgreSQL に格納する."""

from pathlib import Path

import pandas as pd
from sklearn.datasets import fetch_california_housing
from sqlalchemy import create_engine

from ml.common.logging.logger import get_logger
from ml.data.loaders.config import Settings

logger = get_logger(__name__)
DATASET_DIR = Path("ml/data/datasets")
DATASET_PATH = DATASET_DIR / "california_housing.csv"


def _load_or_create_dataset() -> pd.DataFrame:
    """datasets 配下の seed データを読み込む。なければ作成して保存する。"""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    if DATASET_PATH.exists():
        logger.info("Loading seed dataset from %s", DATASET_PATH)
        return pd.read_csv(DATASET_PATH)

    logger.info("Seed dataset not found. Fetching from sklearn and saving to %s", DATASET_PATH)
    data = fetch_california_housing(as_frame=True)
    df = data.frame  # type: ignore[union-attr]
    # ターゲット列名を設計書に合わせる
    df = df.rename(columns={"MedHouseVal": "Price"})
    df.to_csv(DATASET_PATH, index=False)
    return df


def main() -> None:
    settings = Settings()
    df = _load_or_create_dataset()

    # 8:2 で train/test 分割（再現性のため固定シード）
    train_df = df.sample(frac=0.8, random_state=42)
    test_df = df.drop(train_df.index)

    engine = create_engine(settings.postgres_dsn, future=True)
    with engine.begin() as conn:
        train_df.to_sql("training_data", conn, if_exists="replace", index=False)
        test_df.to_sql("test_data", conn, if_exists="replace", index=False)

    logger.info("Seeded %s", settings.postgres_dsn)
    logger.info("  dataset_path:  %s", DATASET_PATH)
    logger.info("  training_data: %d rows", len(train_df))
    logger.info("  test_data:     %d rows", len(test_df))


if __name__ == "__main__":
    main()
