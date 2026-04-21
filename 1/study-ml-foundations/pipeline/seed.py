"""sklearn California Housing データを PostgreSQL に格納するスクリプト."""

from sklearn.datasets import fetch_california_housing
from sqlalchemy import create_engine

from common import get_logger
from pipeline.config import Settings

logger = get_logger(__name__)


def seed() -> None:
    settings = Settings()

    data = fetch_california_housing(as_frame=True)
    df = data.frame  # type: ignore[union-attr]
    # ターゲット列名を設計書に合わせる
    df = df.rename(columns={"MedHouseVal": "Price"})

    # 8:2 で train/test 分割（再現性のため固定シード）
    train_df = df.sample(frac=0.8, random_state=42)
    test_df = df.drop(train_df.index)

    engine = create_engine(settings.postgres_dsn, future=True)
    with engine.begin() as conn:
        train_df.to_sql("training_data", conn, if_exists="replace", index=False)
        test_df.to_sql("test_data", conn, if_exists="replace", index=False)

    logger.info("Seeded %s", settings.postgres_dsn)
    logger.info("  training_data: %d rows", len(train_df))
    logger.info("  test_data:     %d rows", len(test_df))


if __name__ == "__main__":
    seed()
