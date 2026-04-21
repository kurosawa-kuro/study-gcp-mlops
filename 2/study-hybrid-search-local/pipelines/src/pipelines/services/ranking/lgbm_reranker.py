from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from psycopg.rows import dict_row

from common.core.db import get_db_connection

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

_MODEL = None
_MODEL_MTIME: float | None = None  # 最後にロードした際のファイル更新時刻


def _model_path() -> Path:
    return Path(os.getenv("LGBM_MODEL_PATH", "/app/artifacts/models/lgbm_ranker.txt"))


def _load_model():
    """モデルファイルの mtime が変わっていれば再ロードする。"""
    global _MODEL, _MODEL_MTIME

    path = _model_path()
    if not path.exists():
        _MODEL = None
        _MODEL_MTIME = None
        return None

    try:
        current_mtime = path.stat().st_mtime
    except OSError:
        _MODEL = None
        _MODEL_MTIME = None
        return None

    if _MODEL is not None and _MODEL_MTIME == current_mtime:
        return _MODEL

    try:
        import lightgbm as lgb
    except Exception:  # noqa: BLE001
        _MODEL = None
        _MODEL_MTIME = None
        return None

    _MODEL = lgb.Booster(model_file=str(path))
    _MODEL_MTIME = current_mtime
    return _MODEL


def fetch_feature_map(property_ids: list[int]) -> dict[int, dict]:
    if not property_ids:
        return {}

    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    property_id,
                    price,
                    walk_min,
                    age,
                    area,
                    ctr,
                    fav_rate,
                    inquiry_rate,
                    me5_score,
                    popularity_score
                FROM property_features
                WHERE property_id = ANY(%s);
                """,
                (property_ids,),
            )
            rows = cur.fetchall()

    result: dict[int, dict] = {}
    for row in rows:
        result[int(row["property_id"])] = dict(row)
    return result


def rerank_with_lgbm(items: list[dict]) -> list[dict]:
    if not items:
        return items

    ids = [int(item["id"]) for item in items if item.get("id") is not None]
    feature_map = fetch_feature_map(ids)
    model = _load_model()

    vectors: list[list[float]] = []
    scored_items: list[dict] = []

    for item in items:
        property_id = item.get("id")
        if property_id is None:
            continue

        feature = feature_map.get(int(property_id), {})
        vector = [
            float(feature.get("price", item.get("price", 0) or 0)),
            float(feature.get("walk_min", item.get("walk_min", 0) or 0)),
            float(feature.get("age", 0)),
            float(feature.get("area", 0)),
            float(feature.get("ctr", 0)),
            float(feature.get("fav_rate", 0)),
            float(feature.get("inquiry_rate", 0)),
            float(item.get("me5_score", feature.get("me5_score", 0) or 0)),
        ]

        vectors.append(vector)
        scored_items.append(item)

    if not scored_items:
        return items

    matrix = np.asarray(vectors, dtype=np.float32)

    if model is not None:
        predictions = model.predict(matrix)
        for idx, item in enumerate(scored_items):
            item["lgbm_score"] = float(round(float(predictions[idx]), 6))
    else:
        for idx, item in enumerate(scored_items):
            fallback_score = (
                vectors[idx][4] * 0.4
                + vectors[idx][5] * 0.2
                + vectors[idx][6] * 0.2
                + vectors[idx][7] * 0.2
            )
            item["lgbm_score"] = float(round(fallback_score, 6))

    scored_items.sort(key=lambda x: x.get("lgbm_score", 0.0), reverse=True)
    return scored_items
