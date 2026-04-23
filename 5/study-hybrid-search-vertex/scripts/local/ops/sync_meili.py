"""Meilisearch index sync CLI.

Reads ``feature_mart.properties_cleaned`` from BigQuery and upserts documents
into Meilisearch index ``properties``. Invoked as a one-shot job from Cloud
Run Jobs or locally via ``make sync-meili``.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.oauth2 import id_token


def _log(msg: str) -> None:
    """Dual-stream log so Cloud Logging captures it even when stdout is swallowed."""
    print(f"[sync_meili] {msg}", flush=True)
    print(f"[sync_meili] {msg}", file=sys.stderr, flush=True)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync properties_cleaned -> Meilisearch")
    parser.add_argument("--project-id", default="mlops-dev-a")
    parser.add_argument("--table", default="feature_mart.properties_cleaned")
    parser.add_argument("--meili-base-url", required=True)
    parser.add_argument("--index", default="properties")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--require-identity-token", action="store_true", default=False)
    parser.add_argument("--api-key", default="")
    return parser.parse_args(argv)


def _headers(*, base_url: str, api_key: str, require_identity_token: bool) -> dict[str, str]:
    headers = {"content-type": "application/json"}
    if api_key:
        headers["x-meili-api-key"] = api_key
        _log("using api_key auth")
    if require_identity_token:
        _log(f"fetching id_token audience={base_url}")
        try:
            token = id_token.fetch_id_token(Request(), base_url)
        except Exception:
            _log(
                "id_token.fetch_id_token FAILED — check the runtime identity (ADC / metadata server)"
            )
            _log(traceback.format_exc())
            raise
        _log(f"id_token OK (len={len(token)})")
        headers["authorization"] = f"Bearer {token}"
    return headers


def _load_rows(*, client: bigquery.Client, table: str) -> list[dict[str, Any]]:
    # Phase 5 の properties_cleaned スキーマは `description` 列を持たない
    # (seed_minimal の 10 列: property_id/title/city/ward/rent/layout/walk_min/
    # age_years/area_m2/pet_ok)。city / ward / title で lexical 寄与が得られる。
    query = f"""
        SELECT
          property_id,
          title,
          city,
          ward,
          layout,
          rent,
          walk_min,
          age_years,
          pet_ok
        FROM `{table}`
    """
    _log(f"BQ query against {table}")
    rows = client.query(query).result()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "property_id": row["property_id"],
                "title": row["title"],
                "city": row["city"],
                "ward": row["ward"],
                "layout": row["layout"],
                "rent": row["rent"],
                "walk_min": row["walk_min"],
                "age_years": row["age_years"],
                "pet_ok": row["pet_ok"],
            }
        )
    _log(f"loaded {len(out)} rows from BQ")
    return out


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _log("STEP 1 — args parsed")
    _log(f"  project_id={args.project_id} table={args.table} index={args.index}")
    _log(f"  meili_base_url={args.meili_base_url}")
    _log(f"  require_identity_token={args.require_identity_token} batch_size={args.batch_size}")

    fq_table = args.table
    if "." in args.table and args.table.count(".") == 1:
        fq_table = f"{args.project_id}.{args.table}"
    _log(f"  fq_table={fq_table}")

    _log("STEP 2 — BigQuery client init")
    bq = bigquery.Client(project=args.project_id)

    _log("STEP 3 — query BigQuery")
    rows = _load_rows(client=bq, table=fq_table)
    if not rows:
        _log("no rows to sync; returning 0")
        return 0

    _log("STEP 4 — build headers + Meili client")
    headers = _headers(
        base_url=args.meili_base_url,
        api_key=args.api_key,
        require_identity_token=args.require_identity_token,
    )
    base = args.meili_base_url.rstrip("/")

    with httpx.Client(timeout=30.0) as client:
        _log("STEP 5 — PATCH index settings")
        settings_url = f"{base}/indexes/{args.index}/settings"
        _log(f"  settings_url={settings_url}")
        settings_resp = client.patch(
            settings_url,
            json={
                "filterableAttributes": ["rent", "walk_min", "age_years", "layout", "pet_ok"],
                "searchableAttributes": ["title", "description", "layout"],
            },
            headers=headers,
        )
        _log(
            f"  settings response status={settings_resp.status_code} body={settings_resp.text[:200]}"
        )
        settings_resp.raise_for_status()

        _log(f"STEP 6 — PUT documents in batches of {args.batch_size}")
        for i in range(0, len(rows), args.batch_size):
            batch = rows[i : i + args.batch_size]
            url = f"{base}/indexes/{args.index}/documents"
            _log(f"  batch [{i}:{i + len(batch)}] -> {url}")
            put_resp = client.put(url, json=batch, headers=headers)
            _log(f"  batch response status={put_resp.status_code} body={put_resp.text[:200]}")
            put_resp.raise_for_status()

    _log(f"STEP 7 — DONE. Upserted {len(rows)} documents")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    try:
        count = run(argv)
        print(f"synced_documents={count}")
    except Exception as exc:
        _log(f"UNCAUGHT EXCEPTION: {exc}")
        _log(traceback.format_exc())
        print(f"sync_failed={exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
