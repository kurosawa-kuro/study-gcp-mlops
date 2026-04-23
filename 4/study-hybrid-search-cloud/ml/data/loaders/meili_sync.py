"""Meilisearch index sync CLI.

Reads feature_mart.properties_cleaned from BigQuery and upserts documents into
Meilisearch index `properties`.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.oauth2 import id_token


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync properties_cleaned -> Meilisearch")
    parser.add_argument("--project-id", default="mlops-dev-a")
    parser.add_argument("--table", default="feature_mart.properties_cleaned")
    parser.add_argument("--meili-base-url", required=True)
    parser.add_argument("--index", default="properties")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--require-identity-token", action="store_true", default=False)
    parser.add_argument("--impersonate-service-account", default="")
    parser.add_argument("--api-key", default="")
    return parser.parse_args(argv)


def _headers(
    *,
    base_url: str,
    api_key: str,
    require_identity_token: bool,
    impersonate_service_account: str,
) -> dict[str, str]:
    headers = {"content-type": "application/json"}
    if api_key:
        headers["x-meili-api-key"] = api_key
    if require_identity_token:
        token = _resolve_identity_token(
            base_url=base_url,
            impersonate_service_account=impersonate_service_account,
        )
        # Cloud Run consumes Authorization for IAM and does not forward it to
        # the container. Use X-Serverless-Authorization so Meilisearch still
        # receives its own Authorization header semantics.
        headers["x-serverless-authorization"] = f"Bearer {token}"
    return headers


def _resolve_identity_token(*, base_url: str, impersonate_service_account: str) -> str:
    """Prefer ADC ID token, then gcloud ID/access token fallbacks."""
    try:
        return id_token.fetch_id_token(Request(), base_url)
    except Exception:
        pass

    # User-account auth in local terminals often cannot mint audience-bound
    # ID tokens. Fall back progressively to keep local verification unblocked.
    cmd = ["gcloud", "auth", "print-identity-token", f"--audiences={base_url}"]
    if impersonate_service_account:
        cmd.append(f"--impersonate-service-account={impersonate_service_account}")
    try:
        proc = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError:
        # Local operators may not have token-creator on the target SA.
        # Fall back to caller identity token to keep verification unblocked.
        if not impersonate_service_account:
            raise
        fallback_cmd = ["gcloud", "auth", "print-identity-token", f"--audiences={base_url}"]
        try:
            proc = subprocess.run(fallback_cmd, check=True, text=True, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            try:
                # User principals can often mint plain ID tokens even when
                # audience-bound tokens are unavailable.
                proc = subprocess.run(
                    ["gcloud", "auth", "print-identity-token"],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                )
            except subprocess.CalledProcessError:
                # Last resort: OAuth access token.
                proc = subprocess.run(
                    ["gcloud", "auth", "print-access-token"],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                )
    token = (proc.stdout or "").strip()
    if not token:
        raise RuntimeError("failed to mint identity token via gcloud auth")
    return token


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
    rows = client.query(query).result()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "property_id": row["property_id"],
                "title": row["title"],
                "description": row["description"],
                "layout": row["layout"],
                "rent": row["rent"],
                "walk_min": row["walk_min"],
                "age_years": row["age_years"],
                "pet_ok": row["pet_ok"],
            }
        )
    return out


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    fq_table = args.table
    if "." in args.table and args.table.count(".") == 1:
        fq_table = f"{args.project_id}.{args.table}"

    bq = bigquery.Client(project=args.project_id)
    rows = _load_rows(client=bq, table=fq_table)
    if not rows:
        return 0

    headers = _headers(
        base_url=args.meili_base_url,
        api_key=args.api_key,
        require_identity_token=args.require_identity_token,
        impersonate_service_account=args.impersonate_service_account.strip(),
    )
    base = args.meili_base_url.rstrip("/")

    with httpx.Client(timeout=30.0) as client:
        settings_url = f"{base}/indexes/{args.index}/settings"
        settings_resp = client.patch(
            settings_url,
            json={
                "filterableAttributes": ["rent", "walk_min", "age_years", "layout", "pet_ok"],
                "searchableAttributes": ["title", "description", "layout"],
            },
            headers=headers,
        )
        settings_resp.raise_for_status()
        _wait_task_if_needed(
            client=client,
            base=base,
            headers=headers,
            response=settings_resp,
            index=args.index,
        )

        for i in range(0, len(rows), args.batch_size):
            batch = rows[i : i + args.batch_size]
            url = f"{base}/indexes/{args.index}/documents"
            put_resp = client.put(url, json=batch, headers=headers)
            put_resp.raise_for_status()
            _wait_task_if_needed(
                client=client,
                base=base,
                headers=headers,
                response=put_resp,
                index=args.index,
            )

    return len(rows)


def _wait_task_if_needed(
    *,
    client: httpx.Client,
    base: str,
    headers: dict[str, str],
    response: httpx.Response,
    index: str,
    timeout_sec: int = 30,
    poll_sec: float = 0.5,
) -> None:
    """Wait for Meilisearch async task completion when API returns 202."""
    if response.status_code != 202:
        return

    try:
        body = response.json()
    except ValueError:
        body = {}
    task_uid = body.get("taskUid") or body.get("uid")
    if not task_uid:
        # Cloud Run/GFE occasionally returns a 202 body without taskUid.
        # Recover by querying latest task for this index with short retries.
        task_uid = _resolve_latest_task_uid_with_retry(
            client=client,
            base=base,
            headers=headers,
            index=index,
            timeout_sec=timeout_sec,
            poll_sec=poll_sec,
        )
    if not task_uid:
        raise RuntimeError("meili response missing taskUid for async operation")

    deadline = time.monotonic() + timeout_sec
    task_url = f"{base}/tasks/{task_uid}"
    while time.monotonic() < deadline:
        task_resp = client.get(task_url, headers=headers)
        task_resp.raise_for_status()
        task = task_resp.json()
        status = task.get("status")
        if status == "succeeded":
            return
        if status == "failed":
            raise RuntimeError(f"meili task {task_uid} failed: {task}")
        time.sleep(poll_sec)
    raise RuntimeError(f"meili task {task_uid} did not complete within {timeout_sec}s")


def _resolve_latest_task_uid(
    *,
    client: httpx.Client,
    base: str,
    headers: dict[str, str],
    index: str,
) -> int | None:
    task_list_url = f"{base}/tasks"
    for params in (
        {"indexUids": index, "limit": 1},
        {"indexUid": index, "limit": 1},
        {"indexUids[]": index, "limit": 1},
    ):
        resp = client.get(task_list_url, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        results = payload.get("results") if isinstance(payload, dict) else None
        if not results:
            continue
        latest = results[0]
        if not isinstance(latest, dict):
            continue
        uid = latest.get("uid")
        if uid is not None:
            return uid
    return None


def _resolve_latest_task_uid_with_retry(
    *,
    client: httpx.Client,
    base: str,
    headers: dict[str, str],
    index: str,
    timeout_sec: int,
    poll_sec: float,
) -> int | None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        uid = _resolve_latest_task_uid(client=client, base=base, headers=headers, index=index)
        if uid is not None:
            return uid
        time.sleep(poll_sec)
    return None


def main(argv: list[str] | None = None) -> int:
    try:
        count = run(argv)
        print(f"synced_documents={count}")
    except Exception as exc:
        print(f"sync_failed={exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
