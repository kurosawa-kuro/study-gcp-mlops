from __future__ import annotations

from typing import Any, Mapping

from psycopg.rows import dict_row

from common.core.db import get_db_connection

OFFLINE_EVAL_FIELDS = (
    "evaluated_queries",
    "ndcg10_meili",
    "ndcg10_lgbm",
    "map_meili",
    "map_lgbm",
    "recall20_meili",
    "recall20_lgbm",
)


def insert_offline_eval_report(metrics: Mapping[str, float | int]) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO offline_eval_reports (
                    evaluated_queries,
                    ndcg10_meili,
                    ndcg10_lgbm,
                    map_meili,
                    map_lgbm,
                    recall20_meili,
                    recall20_lgbm
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    evaluated_queries,
                    ndcg10_meili,
                    ndcg10_lgbm,
                    map_meili,
                    map_lgbm,
                    recall20_meili,
                    recall20_lgbm,
                    created_at;
                """,
                tuple(metrics[field] for field in OFFLINE_EVAL_FIELDS),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row)


def latest_adoption_decision() -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, adopt_lgbm, reason, evaluated_at
                FROM model_adoption_decisions
                ORDER BY id DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
    return dict(row) if row is not None else None
