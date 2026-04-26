"""No-op experiment tracker.

Experiment metadata is captured via structured Cloud Logging + BigQuery
(``mlops.training_runs``). This stub satisfies the ``ExperimentTracker``
Protocol so callers require no further changes.
"""

from __future__ import annotations

from types import TracebackType

from common.logging import get_logger

logger = get_logger(__name__)


class NoopExperimentTracker:
    """Experiment tracker that discards all metrics (logs at DEBUG level only)."""

    def __enter__(self) -> NoopExperimentTracker:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass

    def log_metrics(self, metrics: dict[str, float]) -> None:
        logger.debug("metrics: %s", metrics)
