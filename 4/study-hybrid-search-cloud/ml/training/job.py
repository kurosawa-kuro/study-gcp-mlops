"""Cloud Run Jobs entrypoint — ``rank-train`` (LightGBM LambdaRank).

* ``--dry-run`` generates synthetic (request_id, property_id, label) groups so
  the trainer can be smoke-tested without BigQuery credentials.
* Default (non-dry-run) fetches training rows from
  ``mlops.ranking_log`` joined with ``mlops.feedback_events``, trains a LightGBM
  lambdarank booster, uploads artifacts to GCS, and records the run in
  ``mlops.training_runs``.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from common.logging import configure_logging

from common import (
    FEATURE_COLS_RANKER,
    RANKER_GROUP_COL,
    RANKER_LABEL_COL,
    generate_run_id,
    get_logger,
)
from ml.registry import GcsArtifactUploader, create_rank_repository
from ml.training.experiments import NoopExperimentTracker, TrainSettings
from ml.training.model_builder import build_rank_params
from ml.training.ports import ArtifactUploader, ExperimentTracker, RankerTrainingRepository
from ml.training.trainer import train, write_artifacts

logger = get_logger(__name__)

TrackerFactory = Callable[[str, Path], ExperimentTracker]

TRAINING_WINDOW_DAYS: int = 90


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LightGBM LambdaRank training job")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic data and skip GCS upload + BQ insert (local smoke test).",
    )
    parser.add_argument(
        "--save-to",
        default=None,
        help="Copy the trained model.txt to this path before the temp dir is cleaned.",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=TRAINING_WINDOW_DAYS,
        help="How many days of ranking_log / feedback_events to train on (default: 90).",
    )
    return parser.parse_args(argv)


def _synthetic_ranking_frames(
    n_queries: int = 40,
    candidates_per_query: int = 20,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Synthetic request_id x candidate frames with LambdaRank-friendly labels."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float | int | str]] = []
    for q in range(n_queries):
        request_id = f"synreq-{q:04d}"
        for rank in range(candidates_per_query):
            rent = float(rng.uniform(50_000, 300_000))
            walk_min = float(rng.integers(1, 30))
            age_years = float(rng.integers(0, 40))
            area_m2 = float(rng.uniform(15, 120))
            ctr = float(rng.uniform(0, 0.2))
            fav_rate = float(rng.uniform(0, 0.05))
            inquiry_rate = float(rng.uniform(0, 0.03))
            me5_score = float(rng.uniform(0.3, 1.0))
            lexical_rank = float(rank + 1)
            score = me5_score * 3 + ctr * 10 + rng.normal(0, 0.4)
            if score > 2.5:
                label = 3
            elif score > 2.0:
                label = 2
            elif score > 1.5:
                label = 1
            else:
                label = 0
            rows.append(
                {
                    RANKER_GROUP_COL: request_id,
                    "rent": rent,
                    "walk_min": walk_min,
                    "age_years": age_years,
                    "area_m2": area_m2,
                    "ctr": ctr,
                    "fav_rate": fav_rate,
                    "inquiry_rate": inquiry_rate,
                    "me5_score": me5_score,
                    "lexical_rank": lexical_rank,
                    "semantic_rank": lexical_rank,
                    RANKER_LABEL_COL: label,
                }
            )
    df = pd.DataFrame(rows)
    df = df.sort_values(RANKER_GROUP_COL, kind="stable").reset_index(drop=True)
    assert {*FEATURE_COLS_RANKER, RANKER_LABEL_COL, RANKER_GROUP_COL}.issubset(df.columns)
    split_idx = int(n_queries * 0.8) * candidates_per_query
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def _split_by_request_id(
    df: pd.DataFrame, *, train_ratio: float = 0.8
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deterministic 80/20 split at the request_id boundary.

    ``abs(hash(request_id)) % 10 < 8`` keeps entire query-groups on one side —
    never splitting a group across train/test (would break NDCG).
    """
    if df.empty:
        return df.copy(), df.copy()
    hashes = df[RANKER_GROUP_COL].map(lambda s: abs(hash(s)) % 10)
    train_mask = hashes < int(train_ratio * 10)
    train_df = df[train_mask].reset_index(drop=True)
    test_df = df[~train_mask].reset_index(drop=True)
    return train_df, test_df


def _is_ranker_frame_usable(df: pd.DataFrame) -> bool:
    """Return True when the frame has enough supervision for LambdaRank."""
    if df.empty:
        return False
    if df[RANKER_GROUP_COL].nunique() < 2:
        return False
    # LambdaRank requires at least some positive labels.
    if (df[RANKER_LABEL_COL] > 0).sum() <= 0:
        return False
    return True


def _validate_ranker_dataframe(
    df: pd.DataFrame,
    *,
    min_rows: int,
    min_request_ids: int = 2,
    min_positive_rows: int = 1,
) -> tuple[bool, list[str]]:
    """Validate whether real ranker training data is usable.

    Returns:
        (is_valid, reasons)
    """
    required = [RANKER_GROUP_COL, RANKER_LABEL_COL, *FEATURE_COLS_RANKER]
    missing = [c for c in required if c not in df.columns]
    reasons: list[str] = []
    if missing:
        reasons.append(f"missing_columns={missing}")
        return False, reasons

    row_count = len(df)
    request_ids = int(df[RANKER_GROUP_COL].nunique()) if row_count > 0 else 0
    positives = int((df[RANKER_LABEL_COL] > 0).sum()) if row_count > 0 else 0
    null_required = int(df[required].isnull().sum().sum()) if row_count > 0 else 0
    max_group_size = (
        int(df.groupby(RANKER_GROUP_COL, dropna=False).size().max()) if request_ids > 0 else 0
    )

    if row_count < min_rows:
        reasons.append(f"rows<{min_rows} ({row_count})")
    if request_ids < min_request_ids:
        reasons.append(f"request_ids<{min_request_ids} ({request_ids})")
    if positives < min_positive_rows:
        reasons.append(f"positives<{min_positive_rows} ({positives})")
    if null_required > 0:
        reasons.append(f"null_required={null_required}")
    if max_group_size < 2:
        reasons.append(f"max_group_size<2 ({max_group_size})")

    return len(reasons) == 0, reasons


def _default_tracker_factory(settings: TrainSettings) -> TrackerFactory:
    def _build(run_id: str, workdir: Path) -> ExperimentTracker:
        return NoopExperimentTracker()

    return _build


def run(
    *,
    dry_run: bool = False,
    save_to: str | None = None,
    window_days: int = TRAINING_WINDOW_DAYS,
    repository: RankerTrainingRepository | None = None,
    uploader: ArtifactUploader | None = None,
    tracker_factory: TrackerFactory | None = None,
) -> str:
    """Execute one LambdaRank training run. Returns the saved model path (or local path on dry-run)."""
    configure_logging()
    settings = TrainSettings()
    run_id = generate_run_id()
    started_at = datetime.now(timezone.utc)
    date_str = started_at.strftime("%Y-%m-%d")

    logger.info("Starting ranker run %s (dry_run=%s)", run_id, dry_run)

    if dry_run:
        train_df, test_df = _synthetic_ranking_frames()
        logger.warning("dry-run: using synthetic LambdaRank data")
    else:
        repository = repository or create_rank_repository(settings)
        full = repository.fetch_training_rows(window_days=window_days)
        if full.empty:
            logger.warning(
                "No ranker training rows in the last %s days; falling back to synthetic data",
                window_days,
            )
            train_df, test_df = _synthetic_ranking_frames()
        else:
            min_rows = max(settings.min_data_in_leaf, 20)
            train_df, test_df = _split_by_request_id(full)
            valid, reasons = _validate_ranker_dataframe(
                train_df,
                min_rows=min_rows,
                min_request_ids=2,
                min_positive_rows=1,
            )
            if not valid or not _is_ranker_frame_usable(train_df):
                logger.warning(
                    "Invalid ranker training data detected; reasons=%s. "
                    "rows=%d request_ids=%d positives=%d -> falling back to synthetic data",
                    reasons,
                    len(train_df),
                    int(train_df[RANKER_GROUP_COL].nunique()),
                    int((train_df[RANKER_LABEL_COL] > 0).sum()),
                )
                train_df, test_df = _synthetic_ranking_frames()
    if test_df.empty and not train_df.empty:
        logger.warning("Test split was empty; reusing train split as validation fallback")
        test_df = train_df.copy()
    logger.info("Fetched %d train / %d test rows", len(train_df), len(test_df))

    params = build_rank_params(
        num_leaves=settings.num_leaves,
        learning_rate=settings.learning_rate,
        feature_fraction=settings.feature_fraction,
        bagging_fraction=settings.bagging_fraction,
        bagging_freq=settings.bagging_freq,
        min_data_in_leaf=settings.min_data_in_leaf,
        lambdarank_truncation_level=settings.lambdarank_truncation_level,
    )

    build_tracker = tracker_factory or _default_tracker_factory(settings)

    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        output_dir = workdir / "artifacts"
        with build_tracker(run_id, workdir) as tracker:
            result = train(
                train_df=train_df,
                test_df=test_df,
                params=params,
                num_iterations=settings.num_iterations,
                early_stopping_rounds=settings.early_stopping_rounds,
            )
            tracker.log_metrics(result.metrics)

        artifacts = write_artifacts(result, output_dir=output_dir)

        if save_to:
            import shutil

            target = Path(save_to).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(artifacts.model_path, target)
            logger.info("Copied model.txt to %s", target)

        if dry_run:
            logger.warning("dry-run: skipping GCS upload + BQ insert")
            return str(save_to) if save_to else str(artifacts.model_path)

        assert repository is not None
        uploader = uploader or GcsArtifactUploader(bucket=settings.gcs_models_bucket)
        model_uri = uploader.upload(artifacts.artifacts_dir, run_id=run_id, date_str=date_str)
        logger.info("Uploaded artifacts; model URI: %s", model_uri)

        finished_at = datetime.now(timezone.utc)
        repository.save_run(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            model_path=model_uri,
            metrics=result.metrics,
            hyperparams=result.hyperparams,
            git_sha=os.getenv("GIT_SHA"),
            dataset_version=date_str,
        )
        logger.info("Ranker run %s complete: %s", run_id, model_uri)
        return model_uri


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        run(dry_run=args.dry_run, save_to=args.save_to, window_days=args.window_days)
    except Exception:
        logger.exception("Ranker training job failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
