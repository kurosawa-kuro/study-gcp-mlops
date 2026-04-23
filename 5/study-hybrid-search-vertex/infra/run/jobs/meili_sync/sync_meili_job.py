"""One-shot Meilisearch index sync for Cloud Run Jobs (Phase 5 ad-hoc).

Runs as sa-api via the job's serviceAccountName. Reads env vars, queries
BigQuery for `feature_mart.properties_cleaned`, and upserts into the
Meilisearch `properties` index via Cloud Run IAM (ID token audience = Meili
Cloud Run URL, fetched through the worker's metadata server).

Env vars:
  MEILI_BASE_URL   required — https://meili-search-<hash>-<region>.a.run.app
  PROJECT_ID       default: mlops-dev-a
  INDEX_NAME       default: properties
  TABLE_FQN        default: ${PROJECT_ID}.feature_mart.properties_cleaned
  BATCH_SIZE       default: 1000
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.oauth2 import id_token


def _log(msg: str) -> None:
    print(f"[meili-sync-job] {msg}", flush=True)
    print(f"[meili-sync-job] {msg}", file=sys.stderr, flush=True)


def _load_rows(project_id: str, table_fqn: str) -> list[dict[str, Any]]:
    _log(f"BQ query against {table_fqn}")
    bq = bigquery.Client(project=project_id)
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
        FROM `{table_fqn}`
    """
    rows = bq.query(query).result()
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
    _log(f"loaded {len(out)} rows")
    return out


def _fetch_id_token(base_url: str) -> str:
    _log(f"fetch_id_token audience={base_url}")
    try:
        token: str = id_token.fetch_id_token(Request(), base_url)  # type: ignore[no-untyped-call]
    except Exception:
        _log("id_token fetch FAILED — check runtime identity (metadata server / ADC)")
        _log(traceback.format_exc())
        raise
    _log(f"id_token OK len={len(token)}")
    return token


def main() -> int:
    try:
        base = os.environ.get("MEILI_BASE_URL", "").rstrip("/")
        if not base:
            _log("MEILI_BASE_URL is required")
            return 2
        project = os.environ.get("PROJECT_ID", "mlops-dev-a")
        index_name = os.environ.get("INDEX_NAME", "properties")
        table_fqn = os.environ.get(
            "TABLE_FQN", f"{project}.feature_mart.properties_cleaned"
        )
        batch_size = int(os.environ.get("BATCH_SIZE", "1000"))
        _log(
            f"STEP 1 start base={base} project={project} index={index_name} "
            f"table={table_fqn} batch={batch_size}"
        )

        _log("STEP 2 fetch id_token")
        token = _fetch_id_token(base)
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
        }

        _log("STEP 3 load rows from BigQuery")
        rows = _load_rows(project, table_fqn)
        if not rows:
            _log("no rows to sync; exit 0")
            return 0

        with httpx.Client(timeout=30.0) as client:
            _log("STEP 4 PATCH index settings")
            settings_url = f"{base}/indexes/{index_name}/settings"
            _log(f"  url={settings_url}")
            resp = client.patch(
                settings_url,
                json={
                    "filterableAttributes": [
                        "rent",
                        "walk_min",
                        "age_years",
                        "layout",
                        "pet_ok",
                    ],
                    "searchableAttributes": ["title", "city", "ward", "layout"],
                },
                headers=headers,
            )
            _log(f"  status={resp.status_code} body={resp.text[:300]}")
            resp.raise_for_status()

            _log(f"STEP 5 PUT documents in batches of {batch_size}")
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                url = f"{base}/indexes/{index_name}/documents"
                _log(f"  batch [{i}:{i + len(batch)}] -> {url}")
                put = client.put(url, json=batch, headers=headers)
                _log(f"  status={put.status_code} body={put.text[:300]}")
                put.raise_for_status()

        _log(f"STEP 6 DONE upserted={len(rows)}")
        return 0
    except Exception as exc:
        _log(f"UNCAUGHT EXCEPTION: {exc}")
        _log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
