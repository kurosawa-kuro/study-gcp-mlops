from pathlib import Path

import lightgbm as lgb

from ml.common.logging.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    model_path = Path("ml/registry/artifacts/latest/model.lgb")
    if not model_path.exists():
        logger.warning("No model found at %s", model_path)
        return
    _ = lgb.Booster(model_file=str(model_path))
    logger.info("Batch serving job is ready. Implement source/target I/O as needed.")


if __name__ == "__main__":
    main()
