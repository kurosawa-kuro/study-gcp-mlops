"""Meilisearch index sync CLI.

Reads ``feature_mart.properties_cleaned`` from BigQuery and upserts documents
into Meilisearch index ``properties``. Invoked as a one-shot job from Cloud
Run Jobs or locally via ``make sync-meili``.

**過去事故の再発検知用ログ** (Phase 4 Issue F / Phase 5 Run 7):

* Phase 4 Issue F: `PATCH /indexes/properties/settings` が 401 Unauthorized。
  呼び出し主体が `sa-api` と一致せず。`Authorization: Bearer <OIDC>` が
  付いているか、どの audience で minted したかをここで echo する。
* Phase 5 Run 7: 6 経路試して `.dockerignore` の `infra/` で詰まった事故。
  このスクリプト自体ではなく Cloud Run Job 専用 image 経路が本命なので、
  ここでは「呼ばれたら動く」ことを log で可視化する。
* Meilisearch numeric 型厳守 (Phase 5 Run 9): `rent` / `walk_min` / `age_years` は
  int64、`pet_ok` は bool。bq CLI `--format=json` は int を string 化するので
  Python client 経由が必須。ここではその保護を `int(row[...])` で明示する。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.oauth2 import id_token

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="[%(asctime)s] %(levelname)s sync_meili: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sync_meili")


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
        logger.info("header: x-meili-api-key SET (len=%d)", len(api_key))
    if require_identity_token:
        logger.info(
            "minting OIDC identity token for audience=%s (Phase 4 Issue F 対策)",
            base_url,
        )
        try:
            token = id_token.fetch_id_token(Request(), base_url)
        except Exception:
            logger.exception(
                "id_token.fetch_id_token FAILED audience=%s — "
                "run via sa-api impersonation (Cloud Run Job 経路推奨)",
                base_url,
            )
            raise
        headers["authorization"] = f"Bearer {token}"
        logger.info("Authorization: Bearer <token len=%d>", len(token))
    return headers


def _load_rows(*, client: bigquery.Client, table: str) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          property_id,
          title,
          description,
          layout,
          rent,
          walk_min,
          age_years,
          pet_ok
        FROM `{table}`
    """
    logger.info("BQ query table=%s", table)
    start = time.monotonic()
    rows = client.query(query).result()
    out: list[dict[str, Any]] = []
    for row in rows:
        # Phase 5 Run 9 教訓: Meili filter `rent <= 150000` は numeric で
        # ないと壊れる。BQ 側は int64 / bool だが、明示 cast で drift 防止。
        out.append(
            {
                "property_id": row["property_id"],
                "title": row["title"],
                "description": row["description"],
                "layout": row["layout"],
                "rent": int(row["rent"]) if row["rent"] is not None else None,
                "walk_min": int(row["walk_min"]) if row["walk_min"] is not None else None,
                "age_years": int(row["age_years"]) if row["age_years"] is not None else None,
                "pet_ok": bool(row["pet_ok"]) if row["pet_ok"] is not None else None,
            }
        )
    logger.info(
        "BQ query DONE rows=%d elapsed_ms=%.0f (cast: rent/walk_min/age_years=int, pet_ok=bool)",
        len(out),
        (time.monotonic() - start) * 1000,
    )
    return out


def _meili_call(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json: Any,
    headers: dict[str, str],
) -> None:
    logger.info("meili %s %s json_payload_size=%d", method, url, len(str(json)))
    start = time.monotonic()
    try:
        if method == "PATCH":
            response = client.patch(url, json=json, headers=headers)
        elif method == "PUT":
            response = client.put(url, json=json, headers=headers)
        else:
            raise ValueError(f"unsupported method {method}")
    except httpx.HTTPError as exc:
        logger.exception("meili %s FAILED url=%s err=%s", method, url, exc)
        raise
    elapsed_ms = (time.monotonic() - start) * 1000
    if response.status_code >= 400:
        logger.error(
            "meili %s HTTP %d url=%s body[:500]=%r elapsed_ms=%.0f",
            method,
            response.status_code,
            url,
            response.text[:500],
            elapsed_ms,
        )
    response.raise_for_status()
    logger.info(
        "meili %s OK status=%d elapsed_ms=%.0f body[:200]=%r",
        method,
        response.status_code,
        elapsed_ms,
        response.text[:200],
    )


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logger.info(
        "sync_meili START project=%s table=%s base_url=%s index=%s batch_size=%d "
        "require_identity_token=%s api_key_set=%s",
        args.project_id,
        args.table,
        args.meili_base_url,
        args.index,
        args.batch_size,
        args.require_identity_token,
        bool(args.api_key),
    )
    fq_table = args.table
    if "." in args.table and args.table.count(".") == 1:
        fq_table = f"{args.project_id}.{args.table}"
        logger.info("table normalized: %s -> %s", args.table, fq_table)

    bq = bigquery.Client(project=args.project_id)
    rows = _load_rows(client=bq, table=fq_table)
    if not rows:
        logger.warning("BQ returned 0 rows — nothing to sync. Check `make seed-test` first.")
        return 0

    headers = _headers(
        base_url=args.meili_base_url,
        api_key=args.api_key,
        require_identity_token=args.require_identity_token,
    )
    base = args.meili_base_url.rstrip("/")

    with httpx.Client(timeout=30.0) as client:
        settings_url = f"{base}/indexes/{args.index}/settings"
        logger.info("STEP 1 — PATCH settings url=%s", settings_url)
        _meili_call(
            client,
            "PATCH",
            settings_url,
            json={
                "filterableAttributes": ["rent", "walk_min", "age_years", "layout", "pet_ok"],
                "searchableAttributes": ["title", "description", "layout"],
            },
            headers=headers,
        )

        logger.info("STEP 2 — PUT documents in %d-sized batches", args.batch_size)
        for i in range(0, len(rows), args.batch_size):
            batch = rows[i : i + args.batch_size]
            url = f"{base}/indexes/{args.index}/documents"
            logger.info(
                "batch %d/%d (rows %d..%d)",
                i // args.batch_size + 1,
                (len(rows) + args.batch_size - 1) // args.batch_size,
                i,
                i + len(batch) - 1,
            )
            _meili_call(client, "PUT", url, json=batch, headers=headers)

    logger.info("sync_meili DONE synced_documents=%d", len(rows))
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    try:
        count = run(argv)
        print(f"synced_documents={count}")
    except Exception as exc:
        logger.exception("sync_meili FAILED: %s", exc)
        print(f"sync_failed={exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
