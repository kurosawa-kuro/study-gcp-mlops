"""Port for experiment tracking (Vertex Experiments / no-op).

Context-manager semantics so callers can ``with tracker: ...``; the enter
returns the tracker itself for chaining ``log_metrics``. Default implementation:
:class:`NoopExperimentTracker` (metrics are logged to Cloud Logging only).
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from ml.common.logging import get_logger

logger = get_logger(__name__)


class ExperimentTracker(Protocol):
    def __enter__(self) -> ExperimentTracker: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
    def log_metrics(self, metrics: dict[str, float]) -> None: ...


class NoopExperimentTracker:
    """No-op tracker — logs metrics to Cloud Logging, no external SaaS dependency."""

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
        logger.info("Training metrics: %s", metrics)
