"""Phase 6 T8 — CLI / KFP-compatible Gemini description enrichment.

Reads a batch of properties from ``feature_mart.properties_cleaned``,
asks Gemini to produce structured metadata (``tags`` / ``target_audience``
/ ``summary_ja``), and writes the result into
``feature_mart.properties_enriched``. The existing embed / training
pipelines are untouched — this is a standalone, opt-in component. It can
also be wrapped by a KFP component (``pipeline/data_job`` future bolt-on)
when the team decides to run it as part of the daily embed flow.

Usage::

    PROJECT_ID=mlops-dev-a uv run python -m scripts.local.enrichment.run_enrichment \\
        --batch-size 50 --limit 200 --model gemini-1.5-flash

Design notes:
* Calls Gemini one property at a time with a strict JSON-mode prompt. A
  future optimisation can batch N properties per call to save token cost.
* Writes via ``bq insert``-equivalent JSON serialisation through the
  Python client — avoids holding a DataFrame in memory.
* Dedupes by always overwriting rows whose ``property_id`` already exists
  (MERGE semantics).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("scripts.local.enrichment")

PROMPT_TEMPLATE = """\
あなたは不動産リスティングを構造化するアシスタントです。
以下の物件メタデータを読み、JSON のみで回答してください。

スキーマ:
{{
  "tags": [文字列の配列、3-5 件、例: "家族向け", "駅近", "ペット可"],
  "target_audience": "家族" | "単身者" | "学生" | "シニア" | "不明",
  "summary_ja": "80 字以内の日本語の短い紹介"
}}

物件:
property_id: {property_id}
city: {city}
layout: {layout}
rent: {rent}
walk_min: {walk_min}
age_years: {age_years}
area_m2: {area_m2}
pet_ok: {pet_ok}
description: {description}
"""


def _load_properties(
    bq: Any, *, project_id: str, properties_table: str, limit: int
) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          property_id,
          COALESCE(city, '') AS city,
          COALESCE(layout, '') AS layout,
          COALESCE(rent, 0) AS rent,
          COALESCE(walk_min, 0) AS walk_min,
          COALESCE(age_years, 0) AS age_years,
          COALESCE(area_m2, 0.0) AS area_m2,
          COALESCE(pet_ok, FALSE) AS pet_ok,
          COALESCE(description, '') AS description
        FROM `{properties_table}`
        ORDER BY property_id
        LIMIT @limit
    """
    from google.cloud import bigquery

    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    rows = bq.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    return [dict(r) for r in rows]


def _enrich(model: Any, row: dict[str, Any]) -> dict[str, Any] | None:
    from vertexai.generative_models import GenerationConfig

    prompt = PROMPT_TEMPLATE.format(**row)
    try:
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=0.2,
                max_output_tokens=256,
                response_mime_type="application/json",
            ),
        )
    except Exception:
        logger.exception("gemini.generate_content failed property_id=%s", row["property_id"])
        return None
    text = getattr(response, "text", "") or ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("gemini returned non-JSON for property_id=%s: %s", row["property_id"], text)
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _insert_enriched(bq: Any, *, enriched_table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    # Use DML MERGE so reruns overwrite existing rows for the same property_id.
    from google.cloud import bigquery

    temp_table = enriched_table + "__staging"
    job = bq.load_table_from_json(
        rows,
        temp_table,
        job_config=bigquery.LoadJobConfig(
            write_disposition="WRITE_TRUNCATE",
            schema=[
                bigquery.SchemaField("property_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
                bigquery.SchemaField("target_audience", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("summary_ja", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("enriched_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("model_name", "STRING", mode="REQUIRED"),
            ],
        ),
    )
    job.result()

    merge_sql = f"""
        MERGE `{enriched_table}` T
        USING `{temp_table}` S
        ON T.property_id = S.property_id
        WHEN MATCHED THEN UPDATE SET
          tags = S.tags,
          target_audience = S.target_audience,
          summary_ja = S.summary_ja,
          enriched_at = S.enriched_at,
          model_name = S.model_name
        WHEN NOT MATCHED THEN INSERT ROW
    """
    bq.query(merge_sql).result()
    bq.delete_table(temp_table, not_found_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=None)
    parser.add_argument("--properties-table", default=None)
    parser.add_argument("--enriched-table", default=None)
    parser.add_argument("--model", default="gemini-1.5-flash")
    parser.add_argument("--location", default="asia-northeast1")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from scripts._common import env

    project_id = args.project or env("PROJECT_ID")
    if not project_id:
        print("PROJECT_ID not set", file=sys.stderr)
        return 2
    properties_table = args.properties_table or (f"{project_id}.feature_mart.properties_cleaned")
    enriched_table = args.enriched_table or (f"{project_id}.feature_mart.properties_enriched")

    import vertexai
    from google.cloud import bigquery
    from vertexai.generative_models import GenerativeModel

    bq = bigquery.Client(project=project_id)
    vertexai.init(project=project_id, location=args.location)
    model = GenerativeModel(args.model)

    rows = _load_properties(
        bq, project_id=project_id, properties_table=properties_table, limit=args.limit
    )
    logger.info("loaded %d properties to enrich", len(rows))

    now = datetime.now(tz=timezone.utc).isoformat()
    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = _enrich(model, row)
        if enriched is None:
            continue
        tags_raw = enriched.get("tags") or []
        if not isinstance(tags_raw, list):
            tags_raw = []
        out.append(
            {
                "property_id": row["property_id"],
                "tags": [str(t) for t in tags_raw][:5],
                "target_audience": str(enriched.get("target_audience") or "不明"),
                "summary_ja": (str(enriched.get("summary_ja") or ""))[:200],
                "enriched_at": now,
                "model_name": args.model,
            }
        )
        if len(out) >= args.batch_size:
            _insert_enriched(bq, enriched_table=enriched_table, rows=out)
            logger.info("flushed batch of %d enriched rows", len(out))
            out = []
    _insert_enriched(bq, enriched_table=enriched_table, rows=out)
    logger.info("enrichment complete; last batch size=%d", len(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
