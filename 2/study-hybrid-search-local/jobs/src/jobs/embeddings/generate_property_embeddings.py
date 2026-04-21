from __future__ import annotations

from psycopg.rows import dict_row

from common.core.db import get_db_connection
from pipelines.repositories.property_embedding_repository import upsert_property_embeddings
from pipelines.services.embeddings.me5_embedding_service import (
    encode_passages,
    get_embedder,
)


def build_passage(row: dict) -> str:
    return (
        f"物件名: {row['title']}\n"
        f"説明: {row['description']}\n"
        f"エリア: {row['city']} {row.get('ward') or ''}\n"
        f"間取り: {row['layout']}\n"
        f"家賃: {row['price']}円\n"
        f"駅徒歩: {row['walk_min']}分\n"
        f"ペット可: {'はい' if row['pet'] else 'いいえ'}"
    ).strip()


def fetch_active_properties() -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    city,
                    ward,
                    layout,
                    price,
                    walk_min,
                    pet
                FROM properties
                WHERE is_active = TRUE
                ORDER BY id;
                """
            )
            return cur.fetchall()


def run_me5_embedding_batch() -> int:
    rows = fetch_active_properties()
    if not rows:
        return 0

    passages = [build_passage(row) for row in rows]
    vectors = encode_passages(passages)
    model_name = get_embedder().model_name

    records = [
        {
            "property_id": int(row["id"]),
            "model_name": model_name,
            "embedding": vectors[idx],
        }
        for idx, row in enumerate(rows)
    ]

    return upsert_property_embeddings(records)


def main() -> None:
    embedder = get_embedder()
    count = run_me5_embedding_batch()
    print(f"ME5 embedding batch completed: backend={embedder.backend}, model={embedder.model_name}, upserted={count}")


if __name__ == "__main__":
    main()
