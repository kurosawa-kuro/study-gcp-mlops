"""Strict /search component gate for production-like validation.

This script enforces that a single /search response contains:
- non-empty results
- Meilisearch contribution (lexical_rank < 10000) at least one row
- ME5 semantic contribution (semantic_rank < 10000 and me5_score > 0) at least one row
- LightGBM rerank contribution (score is not null) at least one row
"""

from __future__ import annotations

import json
import os

from scripts._common import cloud_run_url, fail, http_json, identity_token, print_pretty


def main() -> int:
    query = os.environ.get("QUERY", "新宿区西新宿 1LDK")
    top_k = int(os.environ.get("TOP_K", "20"))
    max_rent = int(os.environ.get("MAX_RENT", "150000"))

    url = cloud_run_url()
    token = identity_token()
    payload = {"query": query, "filters": {"max_rent": max_rent}, "top_k": top_k}
    status, body = http_json("POST", f"{url}/search", token=token, payload=payload)
    if status != 200:
        return fail(f"component-check search returned HTTP {status}: {body}")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return fail(f"component-check search returned non-JSON body: {body}")

    results = parsed.get("results")
    if not isinstance(results, list) or not results:
        return fail("component-check failed: /search returned empty results")

    lexical_hits = sum(1 for r in results if int(r.get("lexical_rank", 10000)) < 10000)
    semantic_hits = sum(
        1
        for r in results
        if int(r.get("semantic_rank", 10000)) < 10000 and float(r.get("me5_score", 0.0)) > 0.0
    )
    lightgbm_hits = sum(1 for r in results if r.get("score") is not None)

    if lexical_hits <= 0:
        return fail("component-check failed: Meilisearch lexical contribution is zero")
    if semantic_hits <= 0:
        return fail("component-check failed: ME5 semantic contribution is zero")
    if lightgbm_hits <= 0:
        return fail("component-check failed: LightGBM rerank contribution is zero")

    print_pretty(body)
    print(
        "component-check passed: "
        f"lexical_hits={lexical_hits} semantic_hits={semantic_hits} lightgbm_hits={lightgbm_hits}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

