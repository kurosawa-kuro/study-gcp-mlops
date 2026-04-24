"""Training hyperparameter assembly for LambdaRank."""

from __future__ import annotations


def build_rank_params(
    *,
    num_leaves: int,
    learning_rate: float,
    feature_fraction: float,
    bagging_fraction: float,
    bagging_freq: int,
    min_data_in_leaf: int,
    lambdarank_truncation_level: int,
) -> dict[str, object]:
    return {
        "objective": "lambdarank",
        "metric": ["ndcg"],
        "ndcg_eval_at": [5, 10, 20],
        "lambdarank_truncation_level": lambdarank_truncation_level,
        "num_leaves": num_leaves,
        "learning_rate": learning_rate,
        "feature_fraction": feature_fraction,
        "bagging_fraction": bagging_fraction,
        "bagging_freq": bagging_freq,
        "min_data_in_leaf": min_data_in_leaf,
        "verbosity": -1,
    }
