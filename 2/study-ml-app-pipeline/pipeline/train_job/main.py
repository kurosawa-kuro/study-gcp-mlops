"""Train job entrypoint."""

from app.config import Settings
from common.logging import get_logger
from common.run_id import generate_run_id
from ml.container import build_container
from ml.core.feature_engineering import engineer_features
from ml.core.preprocess import preprocess
from ml.core.trainer import train

logger = get_logger(__name__)


def main() -> None:
    settings = Settings()
    container = build_container(settings)
    run_id = generate_run_id()

    train_df = container.dataset.load("train")
    test_df = container.dataset.load("test")

    train_df = engineer_features(preprocess(train_df))
    test_df = engineer_features(preprocess(test_df))

    container.tracker.start(run_id, {"phase": "2", "job": "train"})
    booster, metrics = train(train_df, test_df)
    payload = dict(metrics)
    payload["run_id"] = run_id
    container.model_store.save(run_id, booster, payload)
    container.tracker.log_metrics(payload)
    container.tracker.finish()
    logger.info("Training completed: run_id=%s", run_id)


if __name__ == "__main__":
    main()
