from __future__ import annotations

import csv
from pathlib import Path

from common.core.db import get_db_connection

DATASET_PATH = Path("ml/data/datasets/properties_seed.csv")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "t", "yes", "y"}


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Seed dataset not found: {DATASET_PATH}")

    with DATASET_PATH.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"No rows in seed dataset: {DATASET_PATH}")
        return

    sql = """
        INSERT INTO properties
            (id, title, description, city, ward, price, management_fee, layout, area, age, walk_min, pet)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """

    params = [
        (
            int(r["id"]),
            r["title"],
            r["description"],
            r["city"],
            r["ward"],
            int(r["price"]),
            int(r["management_fee"]),
            r["layout"],
            float(r["area"]),
            int(r["age"]),
            int(r["walk_min"]),
            _parse_bool(r["pet"]),
        )
        for r in rows
    ]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, params)
        conn.commit()

    print(f"Seeded properties from {DATASET_PATH}: {len(params)} rows")


if __name__ == "__main__":
    main()
