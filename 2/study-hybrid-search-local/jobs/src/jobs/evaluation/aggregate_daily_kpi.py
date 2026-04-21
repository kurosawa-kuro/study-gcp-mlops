from __future__ import annotations

import argparse
from datetime import date

from common.core.db import get_db_connection
from pipeline.services.evaluation.kpi_service import compute_kpi_metrics


def upsert_kpi_for_day(target_date: date) -> dict[str, float | int | str]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(jsonb_array_length(result_ids)), 0) AS impressions,
                    COALESCE(SUM(CASE WHEN action_type = 'click' THEN 1 ELSE 0 END), 0) AS clicks,
                    COALESCE(SUM(CASE WHEN action_type = 'favorite' THEN 1 ELSE 0 END), 0) AS favorites,
                    COALESCE(SUM(CASE WHEN action_type = 'inquiry' THEN 1 ELSE 0 END), 0) AS inquiries
                FROM search_logs
                WHERE created_at::date = %s;
                """,
                (target_date,),
            )
            impressions, clicks, favorites, inquiries = cur.fetchone()

            impressions = int(impressions)
            clicks = int(clicks)
            favorites = int(favorites)
            inquiries = int(inquiries)

            metrics = compute_kpi_metrics(
                impressions=impressions,
                clicks=clicks,
                favorites=favorites,
                inquiries=inquiries,
            )

            cur.execute(
                """
                INSERT INTO kpi_daily_stats (
                    stat_date,
                    impressions,
                    clicks,
                    favorites,
                    inquiries,
                    ctr,
                    favorite_rate,
                    inquiry_rate,
                    cvr,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (stat_date) DO UPDATE
                SET
                    impressions = EXCLUDED.impressions,
                    clicks = EXCLUDED.clicks,
                    favorites = EXCLUDED.favorites,
                    inquiries = EXCLUDED.inquiries,
                    ctr = EXCLUDED.ctr,
                    favorite_rate = EXCLUDED.favorite_rate,
                    inquiry_rate = EXCLUDED.inquiry_rate,
                    cvr = EXCLUDED.cvr,
                    updated_at = NOW();
                """,
                (
                    target_date,
                    metrics["impressions"],
                    metrics["clicks"],
                    metrics["favorites"],
                    metrics["inquiries"],
                    metrics["ctr"],
                    metrics["favorite_rate"],
                    metrics["inquiry_rate"],
                    metrics["cvr"],
                ),
            )

        conn.commit()

    return {"stat_date": target_date.isoformat(), **metrics}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate online KPI into kpi_daily_stats")
    parser.add_argument("--date", dest="target_date", default=None, help="target date in YYYY-MM-DD")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_date = date.fromisoformat(args.target_date) if args.target_date else date.today()
    result = upsert_kpi_for_day(target_date)

    print(
        "KPI daily aggregation completed: "
        f"date={result['stat_date']}, impressions={result['impressions']}, clicks={result['clicks']}, "
        f"favorites={result['favorites']}, inquiries={result['inquiries']}, ctr={result['ctr']}, "
        f"favorite_rate={result['favorite_rate']}, inquiry_rate={result['inquiry_rate']}, cvr={result['cvr']}"
    )


if __name__ == "__main__":
    main()
