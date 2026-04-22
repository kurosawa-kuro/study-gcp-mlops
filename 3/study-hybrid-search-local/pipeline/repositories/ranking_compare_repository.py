from __future__ import annotations

from psycopg.types.json import Jsonb

from common.core.db import get_db_connection


def log_ranking_comparison(
    *,
    search_log_id: int,
    meili_result_ids: list[int],
    reranked_result_ids: list[int],
) -> int:
    max_len = min(len(meili_result_ids), len(reranked_result_ids))
    changed_count = sum(1 for i in range(max_len) if meili_result_ids[i] != reranked_result_ids[i])

    top1_changed = False
    if meili_result_ids and reranked_result_ids:
        top1_changed = meili_result_ids[0] != reranked_result_ids[0]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ranking_compare_logs (
                    search_log_id,
                    meili_result_ids,
                    reranked_result_ids,
                    changed_count,
                    top1_changed
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    search_log_id,
                    Jsonb(meili_result_ids),
                    Jsonb(reranked_result_ids),
                    changed_count,
                    top1_changed,
                ),
            )
            compare_log_id = int(cur.fetchone()[0])

        conn.commit()

    return compare_log_id
