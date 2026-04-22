from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """コサイン類似度を計算する。

    ベクトルが正規化済みの場合は内積と等しい。
    次元数が異なる場合（fallback と本物モデルの混在等）は 0.0 を返す。
    """
    if not a or not b:
        return 0.0

    if len(a) != len(b):
        return 0.0

    dot = sum(a[i] * b[i] for i in range(len(a)))
    norm_a = math.sqrt(sum(v * v for v in a))
    norm_b = math.sqrt(sum(v * v for v in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return float(dot / (norm_a * norm_b))
