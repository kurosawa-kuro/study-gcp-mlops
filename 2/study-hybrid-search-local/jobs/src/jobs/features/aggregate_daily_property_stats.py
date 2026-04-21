from __future__ import annotations

from common.clients.meilisearch_client import MeiliClient
from common.core.db import get_db_connection
from pipelines.services.ranking.feature_service import (
    recalculate_property_stats,
    remove_inactive_features,
    upsert_property_features,
)


def start_log(conn, job_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO batch_job_logs (job_name, status, started_at)
            VALUES (%s, 'running', NOW())
            RETURNING id;
            """,
            (job_name,),
        )
        return int(cur.fetchone()[0])


def finish_log(conn, log_id: int, status: str, processed_count: int, error_message: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE batch_job_logs
            SET
                status = %s,
                processed_count = %s,
                error_message = %s,
                finished_at = NOW()
            WHERE id = %s;
            """,
            (status, processed_count, error_message, log_id),
        )


def cleanup_inactive_from_meili() -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM properties WHERE is_active = FALSE ORDER BY id;")
            ids = [int(row[0]) for row in cur.fetchall()]

    if not ids:
        return 0

    client = MeiliClient(index_name="properties")
    client.delete_documents_by_ids(ids)
    return len(ids)


def run_daily_jobs() -> dict[str, int]:
    counts = {
        "stats_recalculated": 0,
        "features_upserted": 0,
        "inactive_features_removed": 0,
        "inactive_meili_removed": 0,
    }

    with get_db_connection() as conn:
        log_id = start_log(conn, "phase4_daily_stats")
        conn.commit()

        try:
            counts["stats_recalculated"] = recalculate_property_stats(conn)
            counts["features_upserted"] = upsert_property_features(conn)
            counts["inactive_features_removed"] = remove_inactive_features(conn)
            conn.commit()

            counts["inactive_meili_removed"] = cleanup_inactive_from_meili()

            processed = sum(counts.values())
            finish_log(conn, log_id, "success", processed)
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            finish_log(conn, log_id, "failed", 0, str(exc))
            conn.commit()
            raise

    return counts


def main() -> None:
    counts = run_daily_jobs()
    print(
        "Daily stats completed: "
        f"stats={counts['stats_recalculated']}, "
        f"features={counts['features_upserted']}, "
        f"inactive_features_removed={counts['inactive_features_removed']}, "
        f"inactive_meili_removed={counts['inactive_meili_removed']}"
    )


if __name__ == "__main__":
    main()
