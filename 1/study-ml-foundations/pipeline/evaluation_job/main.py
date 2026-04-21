import json
from pathlib import Path

from ml.common.logging.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    metrics_path = Path("models/latest/metrics.json")
    if not metrics_path.exists():
        logger.warning("No metrics found at %s", metrics_path)
        return
    metrics = json.loads(metrics_path.read_text())
    logger.info("Latest metrics: rmse=%s, r2=%s", metrics.get("rmse"), metrics.get("r2"))


if __name__ == "__main__":
    main()
