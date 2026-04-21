from __future__ import annotations

from psycopg.rows import dict_row

from common.core.db import get_db_connection


def main() -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM property_features;")
            feature_count = int(cur.fetchone()[0])

            cur.execute("SELECT COUNT(*) FROM batch_job_logs WHERE job_name = 'phase4_daily_stats';")
            job_count = int(cur.fetchone()[0])

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    pf.property_id,
                    p.title,
                    pf.ctr,
                    pf.fav_rate,
                    pf.inquiry_rate,
                    pf.me5_score,
                    pf.popularity_score,
                    pf.updated_at
                FROM property_features pf
                JOIN properties p ON p.id = pf.property_id
                ORDER BY pf.popularity_score DESC, pf.property_id
                LIMIT 5;
                """
            )
            top_rows = cur.fetchall()

    print(f"property_features_count={feature_count}")
    print(f"phase4_daily_job_logs={job_count}")
    print("top5_popular=")
    for row in top_rows:
        print(
            f"  id={row['property_id']} title={row['title']} "
            f"score={row['popularity_score']:.4f} "
            f"ctr={row['ctr']:.4f} fav={row['fav_rate']:.4f} inq={row['inquiry_rate']:.4f} me5={row['me5_score']:.4f}"
        )


if __name__ == "__main__":
    main()
