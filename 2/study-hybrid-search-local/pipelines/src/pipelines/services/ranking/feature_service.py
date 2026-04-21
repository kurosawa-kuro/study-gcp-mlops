from __future__ import annotations

from psycopg import Connection


def recalculate_property_stats(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE property_stats
            SET
                ctr = CASE WHEN impression > 0 THEN click::double precision / impression ELSE 0 END,
                fav_rate = CASE WHEN impression > 0 THEN favorite::double precision / impression ELSE 0 END,
                inquiry_rate = CASE WHEN impression > 0 THEN inquiry::double precision / impression ELSE 0 END,
                updated_at = NOW();
            """
        )
        return cur.rowcount


def upsert_property_features(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH me5 AS (
                SELECT
                    rid.property_id,
                    AVG(ms.me5_score) AS me5_score
                FROM (
                    SELECT
                        sl.id,
                        rid.value::bigint AS property_id,
                        rid.ord
                    FROM search_logs sl,
                    LATERAL jsonb_array_elements_text(sl.result_ids) WITH ORDINALITY AS rid(value, ord)
                ) rid
                JOIN (
                    SELECT
                        sl.id,
                        ms.value::double precision AS me5_score,
                        ms.ord
                    FROM search_logs sl,
                    LATERAL jsonb_array_elements_text(sl.me5_scores) WITH ORDINALITY AS ms(value, ord)
                ) ms
                  ON ms.id = rid.id
                 AND ms.ord = rid.ord
                GROUP BY rid.property_id
            )
            INSERT INTO property_features (
                property_id, price, walk_min, age, area, photo_count,
                ctr, fav_rate, inquiry_rate, me5_score, popularity_score, updated_at
            )
            SELECT
                p.id,
                p.price,
                p.walk_min,
                p.age,
                p.area::double precision,
                0 AS photo_count,
                COALESCE(s.ctr, 0) AS ctr,
                COALESCE(s.fav_rate, 0) AS fav_rate,
                COALESCE(s.inquiry_rate, 0) AS inquiry_rate,
                                COALESCE(m.me5_score, 0) AS me5_score,
                (
                                        COALESCE(s.ctr, 0) * 0.4 +
                                        COALESCE(s.fav_rate, 0) * 0.2 +
                                        COALESCE(s.inquiry_rate, 0) * 0.2 +
                                        COALESCE(m.me5_score, 0) * 0.2
                ) AS popularity_score,
                NOW()
            FROM properties p
            LEFT JOIN property_stats s
              ON s.property_id = p.id
                        LEFT JOIN me5 m
                            ON m.property_id = p.id
            WHERE p.is_active = TRUE
            ON CONFLICT (property_id) DO UPDATE
            SET
                price = EXCLUDED.price,
                walk_min = EXCLUDED.walk_min,
                age = EXCLUDED.age,
                area = EXCLUDED.area,
                photo_count = EXCLUDED.photo_count,
                ctr = EXCLUDED.ctr,
                fav_rate = EXCLUDED.fav_rate,
                inquiry_rate = EXCLUDED.inquiry_rate,
                me5_score = EXCLUDED.me5_score,
                popularity_score = EXCLUDED.popularity_score,
                updated_at = NOW();
            """
        )
        return cur.rowcount


def remove_inactive_features(conn: Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM property_features pf
            USING properties p
            WHERE pf.property_id = p.id
              AND p.is_active = FALSE;
            """
        )
        return cur.rowcount
