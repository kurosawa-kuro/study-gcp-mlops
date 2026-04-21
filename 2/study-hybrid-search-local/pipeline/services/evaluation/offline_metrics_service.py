from __future__ import annotations

import math
from typing import TypedDict

from psycopg.rows import dict_row

from common.core.db import get_db_connection


class OfflineMetrics(TypedDict):
    evaluated_queries: int
    ndcg10_meili: float
    ndcg10_lgbm: float
    map_meili: float
    map_lgbm: float
    recall20_meili: float
    recall20_lgbm: float


def _find_rank(ids: list[int], target: int, k: int) -> int | None:
    for idx, doc_id in enumerate(ids[:k], start=1):
        if int(doc_id) == target:
            return idx
    return None


def _ndcg_at_10(rank: int | None, gain: float) -> float:
    if rank is None:
        return 0.0
    dcg = gain / math.log2(rank + 1)
    idcg = gain / math.log2(2)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def _avg_precision(rank: int | None) -> float:
    if rank is None:
        return 0.0
    return 1.0 / rank


def _recall_at_20(rank: int | None) -> float:
    return 1.0 if rank is not None else 0.0


def compute_offline_metrics(limit: int = 5000) -> OfflineMetrics:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    r.search_log_id,
                    r.meili_result_ids,
                    r.reranked_result_ids,
                    sl.actioned_id,
                    sl.action_type
                FROM ranking_compare_logs r
                JOIN search_logs sl ON sl.id = r.search_log_id
                WHERE sl.actioned_id IS NOT NULL
                  AND sl.action_type IN ('click', 'favorite', 'inquiry')
                ORDER BY r.id DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    if not rows:
        return {
            "evaluated_queries": 0,
            "ndcg10_meili": 0.0,
            "ndcg10_lgbm": 0.0,
            "map_meili": 0.0,
            "map_lgbm": 0.0,
            "recall20_meili": 0.0,
            "recall20_lgbm": 0.0,
        }

    gain_by_action = {
        "click": 1.0,
        "favorite": 2.0,
        "inquiry": 3.0,
    }

    ndcg_meili_sum = 0.0
    ndcg_lgbm_sum = 0.0
    map_meili_sum = 0.0
    map_lgbm_sum = 0.0
    recall_meili_sum = 0.0
    recall_lgbm_sum = 0.0

    for row in rows:
        actioned_id = int(row["actioned_id"])
        action_type = str(row["action_type"])
        gain = gain_by_action.get(action_type, 1.0)

        meili_ids = [int(v) for v in (row["meili_result_ids"] or [])]
        reranked_ids = [int(v) for v in (row["reranked_result_ids"] or [])]

        meili_rank10 = _find_rank(meili_ids, actioned_id, 10)
        lgbm_rank10 = _find_rank(reranked_ids, actioned_id, 10)
        meili_rank20 = _find_rank(meili_ids, actioned_id, 20)
        lgbm_rank20 = _find_rank(reranked_ids, actioned_id, 20)

        ndcg_meili_sum += _ndcg_at_10(meili_rank10, gain)
        ndcg_lgbm_sum += _ndcg_at_10(lgbm_rank10, gain)

        map_meili_sum += _avg_precision(meili_rank20)
        map_lgbm_sum += _avg_precision(lgbm_rank20)

        recall_meili_sum += _recall_at_20(meili_rank20)
        recall_lgbm_sum += _recall_at_20(lgbm_rank20)

    n = float(len(rows))
    return {
        "evaluated_queries": len(rows),
        "ndcg10_meili": round(ndcg_meili_sum / n, 6),
        "ndcg10_lgbm": round(ndcg_lgbm_sum / n, 6),
        "map_meili": round(map_meili_sum / n, 6),
        "map_lgbm": round(map_lgbm_sum / n, 6),
        "recall20_meili": round(recall_meili_sum / n, 6),
        "recall20_lgbm": round(recall_lgbm_sum / n, 6),
    }
