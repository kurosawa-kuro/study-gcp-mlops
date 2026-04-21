"""Backward-compatible wrapper for the training job entrypoint."""

from ml.training.job import (
    TRAINING_WINDOW_DAYS,
    _default_tracker_factory,
    _parse_args,
    _split_by_request_id,
    _synthetic_ranking_frames,
    main,
    run,
)

__all__ = [
    "TRAINING_WINDOW_DAYS",
    "_default_tracker_factory",
    "_parse_args",
    "_split_by_request_id",
    "_synthetic_ranking_frames",
    "main",
    "run",
]
