import argparse
from pathlib import Path

from common.core.db import get_db_connection


def run_sql_file(file_path: Path) -> None:
    sql = file_path.read_text(encoding="utf-8")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute SQL file against PostgreSQL")
    parser.add_argument("sql_file", type=Path)
    args = parser.parse_args()

    if not args.sql_file.exists():
        raise FileNotFoundError(f"SQL file not found: {args.sql_file}")

    run_sql_file(args.sql_file)
    print(f"Applied: {args.sql_file}")


if __name__ == "__main__":
    main()
