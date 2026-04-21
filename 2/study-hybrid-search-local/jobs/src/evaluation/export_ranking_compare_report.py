from __future__ import annotations

from psycopg.rows import dict_row

from common.core.db import get_db_connection


def main() -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ranking_compare_logs;")
            total = int(cur.fetchone()[0])

            cur.execute("SELECT COUNT(*) FROM ranking_compare_logs WHERE top1_changed = TRUE;")
            top1_changed = int(cur.fetchone()[0])

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, search_log_id, changed_count, top1_changed, created_at,
                       meili_result_ids, reranked_result_ids
                FROM ranking_compare_logs
                ORDER BY id DESC
                LIMIT 5;
                """
            )
            rows = cur.fetchall()

    print(f"ranking_compare_total={total}")
    print(f"ranking_compare_top1_changed={top1_changed}")
    print("latest_compare_logs=")
    for row in rows:
        meili_top3 = (row["meili_result_ids"] or [])[:3]
        rerank_top3 = (row["reranked_result_ids"] or [])[:3]
        print(
            f"  id={row['id']} search_log_id={row['search_log_id']} changed={row['changed_count']} "
            f"top1_changed={row['top1_changed']} meili_top3={meili_top3} rerank_top3={rerank_top3}"
        )


if __name__ == "__main__":
    main()
