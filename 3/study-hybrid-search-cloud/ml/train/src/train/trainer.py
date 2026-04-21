"""Backward-compatible wrapper for training logic."""

from ml.training.model_builder import build_rank_params
from ml.training.trainer import (
    RankTrainResult,
    RankTrainingArtifacts,
    _group_sizes,
    train,
    write_artifacts,
)

__all__ = [
    "RankTrainResult",
    "RankTrainingArtifacts",
    "_group_sizes",
    "build_rank_params",
    "train",
    "write_artifacts",
]
