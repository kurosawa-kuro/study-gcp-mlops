"""No-op :class:`ExperimentTracker` adapter (W&B 削除後の stub)。

W&B は Phase 5/6 から除去済。実験ログは BigQuery ``mlops.training_runs`` /
Vertex AI Experiments への dual-write (``BigQueryRankerRepository.save_run``)
で代替する。テストおよびトレーナーが依然 ``NullExperimentTracker`` を参照す
るためこのモジュールは残置するが、``wandb`` には一切依存しない。
"""

from __future__ import annotations

from types import TracebackType


class NullExperimentTracker:
    """何もしない実験トラッカー。context manager として透過的に動作する。"""

    def __enter__(self) -> NullExperimentTracker:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass

    def log_metrics(self, metrics: dict[str, float]) -> None:  # noqa: ARG002
        pass
