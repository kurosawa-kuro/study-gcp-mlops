from __future__ import annotations

import csv
from pathlib import Path

from psycopg.rows import dict_row

from common.core.db import get_db_connection

OUTPUT_PATH = Path("/app/artifacts/train/rank_train.csv")


def fetch_training_rows(log_limit: int = 5000) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH recent_logs AS (
                    SELECT
                        id,
                        query,
                        result_ids,
                        me5_scores,
                        actioned_id,
                        action_type
                    FROM search_logs
                    WHERE jsonb_array_length(result_ids) > 0
                    ORDER BY id DESC
                    LIMIT %s
                ),
                expanded AS (
                    SELECT
                        sl.id AS search_log_id,
                        sl.query,
                        rid.value::bigint AS property_id,
                        rid.ord,
                        COALESCE(ms.value::double precision, 0) AS me5_score,
                        sl.actioned_id,
                        sl.action_type
                    FROM recent_logs sl,
                    LATERAL jsonb_array_elements_text(sl.result_ids) WITH ORDINALITY AS rid(value, ord)
                    LEFT JOIN LATERAL jsonb_array_elements_text(sl.me5_scores) WITH ORDINALITY AS ms(value, ord)
                      ON ms.ord = rid.ord
                )
                SELECT
                    e.search_log_id,
                    e.query,
                    e.property_id,
                    e.ord AS rank_position,
                    pf.price,
                    pf.walk_min,
                    pf.age,
                    pf.area,
                    pf.ctr,
                    pf.fav_rate,
                    pf.inquiry_rate,
                    COALESCE(e.me5_score, pf.me5_score, 0) AS me5_score,
                    CASE
                        WHEN e.actioned_id = e.property_id AND e.action_type = 'inquiry' THEN 3
                        WHEN e.actioned_id = e.property_id AND e.action_type = 'favorite' THEN 2
                        WHEN e.actioned_id = e.property_id AND e.action_type = 'click' THEN 1
                        ELSE 0
                    END AS label
                FROM expanded e
                JOIN property_features pf ON pf.property_id = e.property_id
                ORDER BY e.search_log_id, e.ord;
                """,
                (log_limit,),
            )
            return cur.fetchall()


def write_csv(rows: list[dict], output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "search_log_id",
        "query",
        "property_id",
        "rank_position",
        "price",
        "walk_min",
        "age",
        "area",
        "ctr",
        "fav_rate",
        "inquiry_rate",
        "me5_score",
        "label",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def main() -> None:
    rows = fetch_training_rows()
    output_path = write_csv(rows)
    positive = sum(1 for row in rows if int(row["label"]) > 0)
    print(
        f"Phase5 training data generated: rows={len(rows)}, positive={positive}, "
        f"queries={len(set(int(row['search_log_id']) for row in rows))}, path={output_path}"
    )


if __name__ == "__main__":
    main()
