from __future__ import annotations

from typing import Literal

from psycopg.types.json import Jsonb

from common.core.db import get_db_connection

FeedbackAction = Literal["click", "favorite", "inquiry"]


def log_search_and_increment_impressions(
    *,
    query: str,
    user_id: int | None,
    result_ids: list[int],
    me5_scores: list[float] | None = None,
) -> int:
    if me5_scores is None:
        me5_scores = [0.0 for _ in result_ids]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO search_logs (query, user_id, result_ids, me5_scores)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (query, user_id, Jsonb(result_ids), Jsonb(me5_scores)),
            )
            search_log_id = int(cur.fetchone()[0])

            # バルク UPSERT — 個別ループを廃止してパフォーマンスを改善
            if result_ids:
                cur.execute(
                    """
                    INSERT INTO property_stats (
                        property_id, impression, click, favorite, inquiry,
                        ctr, fav_rate, inquiry_rate, updated_at
                    )
                    SELECT
                        unnest(%s::bigint[]),
                        1, 0, 0, 0, 0, 0, 0, NOW()
                    ON CONFLICT (property_id) DO UPDATE
                    SET
                        impression = property_stats.impression + 1,
                        ctr = CASE
                            WHEN property_stats.impression + 1 > 0
                            THEN property_stats.click::double precision / (property_stats.impression + 1)
                            ELSE 0
                        END,
                        fav_rate = CASE
                            WHEN property_stats.impression + 1 > 0
                            THEN property_stats.favorite::double precision / (property_stats.impression + 1)
                            ELSE 0
                        END,
                        inquiry_rate = CASE
                            WHEN property_stats.impression + 1 > 0
                            THEN property_stats.inquiry::double precision / (property_stats.impression + 1)
                            ELSE 0
                        END,
                        updated_at = NOW();
                    """,
                    (result_ids,),
                )

        conn.commit()

    return search_log_id


def apply_feedback(
    *,
    user_id: int | None,
    property_id: int,
    action: FeedbackAction,
    search_log_id: int | None,
) -> bool:
    click_inc = 1 if action == "click" else 0
    favorite_inc = 1 if action == "favorite" else 0
    inquiry_inc = 1 if action == "inquiry" else 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO property_stats (
                    property_id, impression, click, favorite, inquiry,
                    ctr, fav_rate, inquiry_rate, updated_at
                )
                VALUES (%s, 0, %s, %s, %s, 0, 0, 0, NOW())
                ON CONFLICT (property_id) DO UPDATE
                SET
                    click = property_stats.click + EXCLUDED.click,
                    favorite = property_stats.favorite + EXCLUDED.favorite,
                    inquiry = property_stats.inquiry + EXCLUDED.inquiry,
                    ctr = CASE
                        WHEN property_stats.impression > 0
                        THEN (property_stats.click + EXCLUDED.click)::double precision / property_stats.impression
                        ELSE 0
                    END,
                    fav_rate = CASE
                        WHEN property_stats.impression > 0
                        THEN (property_stats.favorite + EXCLUDED.favorite)::double precision / property_stats.impression
                        ELSE 0
                    END,
                    inquiry_rate = CASE
                        WHEN property_stats.impression > 0
                        THEN (property_stats.inquiry + EXCLUDED.inquiry)::double precision / property_stats.impression
                        ELSE 0
                    END,
                    updated_at = NOW();
                """,
                (property_id, click_inc, favorite_inc, inquiry_inc),
            )

            updated_search_log = True
            if search_log_id is not None:
                cur.execute(
                    """
                    UPDATE search_logs
                    SET
                        clicked_id = CASE WHEN %s = 'click' THEN %s ELSE clicked_id END,
                        actioned_id = %s,
                        action_type = %s
                    WHERE id = %s;
                    """,
                    (action, property_id, property_id, action, search_log_id),
                )
                updated_search_log = cur.rowcount > 0

        conn.commit()

    return updated_search_log
