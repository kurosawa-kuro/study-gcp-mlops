from decimal import Decimal

from psycopg.rows import dict_row

from common.clients.meilisearch_client import MeiliClient
from common.core.db import get_db_connection


def fetch_properties() -> list[dict]:
    query = """
    SELECT
      id,
      title,
      description,
      city,
      ward,
      price,
      layout,
      walk_min,
      pet,
      age,
      area,
      created_at
    FROM properties
        WHERE is_active = TRUE
    ORDER BY id;
    """

    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            rows = cur.fetchall()

    documents = []
    for row in rows:
        doc = dict(row)

        for key, value in list(doc.items()):
            if isinstance(value, Decimal):
                doc[key] = float(value)

        created_at = doc.get("created_at")
        if created_at is not None:
            doc["created_at"] = created_at.isoformat()

        documents.append(doc)

    return documents


def main() -> None:
    client = MeiliClient(index_name="properties")
    client.create_index_if_missing(primary_key="id")
    client.set_filterable_attributes(["city", "layout", "price", "pet", "walk_min", "ward"])

    documents = fetch_properties()
    client.add_documents(documents)

    print(f"Synced {len(documents)} properties to Meilisearch")


if __name__ == "__main__":
    main()
