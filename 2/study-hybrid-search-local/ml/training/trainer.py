from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

TRAIN_CSV_PATH = Path("/app/artifacts/train/rank_train.csv")
MODEL_PATH = Path("/app/artifacts/models/lgbm_ranker.txt")
METADATA_PATH = Path("/app/artifacts/models/lgbm_ranker_metadata.json")

FEATURE_COLUMNS = [
    "price",
    "walk_min",
    "age",
    "area",
    "ctr",
    "fav_rate",
    "inquiry_rate",
    "me5_score",
]


def load_training_data(path: Path = TRAIN_CSV_PATH) -> tuple[np.ndarray, np.ndarray, list[int], int]:
    if not path.exists():
        raise FileNotFoundError(f"training csv not found: {path}")

    features: list[list[float]] = []
    labels: list[float] = []
    group_sizes: list[int] = []

    current_qid: int | None = None
    current_group_size = 0

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = int(row["search_log_id"])

            if current_qid is None:
                current_qid = qid
            if qid != current_qid:
                group_sizes.append(current_group_size)
                current_qid = qid
                current_group_size = 0

            current_group_size += 1
            features.append([float(row[col]) for col in FEATURE_COLUMNS])
            labels.append(float(row["label"]))

    if current_group_size > 0:
        group_sizes.append(current_group_size)

    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(labels, dtype=np.float32)
    positive_count = int(np.sum(y > 0))

    return x, y, group_sizes, positive_count


def train_model() -> dict[str, object]:
    try:
        import lightgbm as lgb
    except OSError as exc:
        raise RuntimeError("lightgbm runtime dependency is missing (libgomp.so.1)") from exc

    x, y, group_sizes, positive_count = load_training_data()

    if x.size == 0:
        raise ValueError("no training rows found")
    if positive_count == 0:
        raise ValueError("no positive labels found; run more feedback before training")

    train_set = lgb.Dataset(x, label=y, group=group_sizes, feature_name=FEATURE_COLUMNS)

    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [10],
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 1,
        "verbosity": -1,
    }

    booster = lgb.train(params, train_set, num_boost_round=80)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(MODEL_PATH))

    metadata = {
        "model_path": str(MODEL_PATH),
        "feature_columns": FEATURE_COLUMNS,
        "rows": int(x.shape[0]),
        "queries": len(group_sizes),
        "positive_rows": positive_count,
    }

    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    metadata = train_model()
    print(
        "Phase5 LightGBM training completed: "
        f"rows={metadata['rows']}, queries={metadata['queries']}, "
        f"positive_rows={metadata['positive_rows']}, model={metadata['model_path']}"
    )


if __name__ == "__main__":
    main()
