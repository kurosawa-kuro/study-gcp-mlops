from __future__ import annotations

from psycopg.rows import dict_row

from common.core.db import get_db_connection


def upsert_property_embeddings(records: list[dict[str, object]]) -> int:
    if not records:
        return 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO property_embeddings (property_id, model_name, embedding, updated_at)
                VALUES (%(property_id)s, %(model_name)s, %(embedding)s, NOW())
                ON CONFLICT (property_id) DO UPDATE
                SET
                    model_name = EXCLUDED.model_name,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW();
                """,
                records,
            )
        conn.commit()

    return len(records)


def fetch_property_embeddings(ids: list[int]) -> dict[int, list[float]]:
    if not ids:
        return {}

    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT property_id, embedding
                FROM property_embeddings
                WHERE property_id = ANY(%s);
                """,
                (ids,),
            )
            rows = cur.fetchall()

    result: dict[int, list[float]] = {}
    for row in rows:
        result[int(row["property_id"])] = [float(v) for v in row["embedding"]]
    return result
