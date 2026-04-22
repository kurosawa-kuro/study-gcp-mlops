"""Smoke-test the deployed /search endpoint. Phase 4 (rerank-free) returns
results where final_rank == lexical_rank and score is null.
Override QUERY / TOP_K / MAX_RENT via env vars.
"""

from __future__ import annotations

import json
import os

from scripts._common import cloud_run_url, fail, http_json, identity_token, print_pretty


def main() -> int:
    query = os.environ.get("QUERY", "新宿区西新宿 1LDK")
    top_k = int(os.environ.get("TOP_K", "20"))
    max_rent = int(os.environ.get("MAX_RENT", "150000"))
    allow_empty = os.environ.get("ALLOW_EMPTY_RESULTS", "0") == "1"

    url = cloud_run_url()
    token = identity_token()
    payload = {"query": query, "filters": {"max_rent": max_rent}, "top_k": top_k}
    status, body = http_json("POST", f"{url}/search", token=token, payload=payload)
    if status != 200:
        return fail(f"search returned HTTP {status}: {body}")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return fail(f"search returned non-JSON body: {body}")
    results = parsed.get("results")
    if isinstance(results, list) and len(results) == 0 and not allow_empty:
        return fail(
            "search returned 200 but results is empty; "
            "check seed/sync state (set ALLOW_EMPTY_RESULTS=1 to bypass)"
        )
    print_pretty(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
