"""学習パイプライン エントリーポイント.

実行: python3 -m pipeline.training_job.main
"""

from ml.common.logging.logger import get_logger
from ml.common.utils.run_id import generate_run_id
from ml.data.feature_engineering.feature_engineering import engineer_features
from ml.data.loaders.config import Settings
from ml.data.loaders.repository import get_repository
from ml.data.preprocess.preprocess import preprocess
from ml.evaluation import init_wandb, log_metrics
from ml.evaluation.config import EvalSettings
from ml.training.trainer import train

logger = get_logger(__name__)


def main() -> None:
    settings = Settings()
    eval_settings = EvalSettings()
    run_id = generate_run_id()

    # データ取得
    try:
        repo = get_repository(settings)
        logger.info("Loading data...")
        train_df = repo.fetch_train()
        test_df = repo.fetch_test()
        if train_df.empty or test_df.empty:
            logger.error("Data is empty (train=%d, test=%d)", len(train_df), len(test_df))
            raise SystemExit(1)
        logger.info("train: %d rows, test: %d rows", len(train_df), len(test_df))
    except SystemExit:
        raise
    except Exception as e:
        logger.error("Failed to load data: %s", e)
        raise SystemExit(1) from e

    # 前処理
    logger.info("Preprocessing...")
    train_df = preprocess(train_df)
    test_df = preprocess(test_df)

    # 特徴量エンジニアリング
    logger.info("Feature engineering...")
    train_df = engineer_features(train_df)
    test_df = engineer_features(test_df)

    # W&B 初期化
    try:
        init_wandb(eval_settings.wandb_api_key, eval_settings.wandb_project)
    except Exception as e:
        logger.warning("W&B initialization failed, continuing without it: %s", e)

    # 学習
    try:
        metrics = train(train_df, test_df, settings.model_dir, run_id)
    except Exception as e:
        logger.error("Training failed: %s", e)
        raise SystemExit(1) from e

    # 精度を PostgreSQL に記録
    try:
        repo.save_run(run_id, metrics)
        logger.info("Run saved to PostgreSQL: %s", run_id)
    except Exception as e:
        logger.warning("Failed to save run to PostgreSQL: %s", e)

    # メトリクスログ
    try:
        log_metrics(metrics)
    except Exception as e:
        logger.warning("Failed to log metrics to W&B: %s", e)

    logger.info("Done.")


if __name__ == "__main__":
    main()
