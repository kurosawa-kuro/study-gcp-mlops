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


def _diagnose_semantic_zero(results: list[dict], *, readyz_payload: dict | None) -> str:
    all_semantic_default = all(int(r.get("semantic_rank", 10000)) >= 10000 for r in results)
    all_me5_zero = all(float(r.get("me5_score", 0.0)) <= 0.0 for r in results)
    rerank_enabled = None
    if isinstance(readyz_payload, dict):
        rerank_enabled = readyz_payload.get("rerank_enabled")
    if all_semantic_default and all_me5_zero:
        return (
            "ME5 semantic contribution is zero. likely branch: "
            "app.api.main.search -> encoder is None -> query_vector=[] -> "
            "candidate_retriever retrieves lexical-only and fills defaults "
            "(semantic_rank=10000, me5_score=0.0). "
            f"readyz.rerank_enabled={rerank_enabled}"
        )
    return (
        "ME5 semantic contribution is zero. semantic candidates were not observed "
        "in /search results. check encoder load, query/filter suitability, and "
        "feature_mart.property_embeddings coverage."
    )


def main() -> int:
    query = os.environ.get("QUERY", "新宿区西新宿 1LDK")
    top_k = int(os.environ.get("TOP_K", "20"))
    max_rent = int(os.environ.get("MAX_RENT", "150000"))
    target = os.environ.get("TARGET", "gcp").strip().lower()

    if target == "local":
        url = os.environ.get("LOCAL_API_URL", "http://127.0.0.1:8080").rstrip("/")
        token = None
    elif target == "gcp":
        url = cloud_run_url()
        token = identity_token()
    else:
        return fail("component-check config error: TARGET must be either 'local' or 'gcp'")

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
    typed_results: list[dict] = [r for r in results if isinstance(r, dict)]
    readyz_payload: dict | None = None
    readyz_status, readyz_body = http_json("GET", f"{url}/readyz", token=token)
    if readyz_status == 200:
        try:
            payload_obj = json.loads(readyz_body)
            if isinstance(payload_obj, dict):
                readyz_payload = payload_obj
        except json.JSONDecodeError:
            readyz_payload = None

    lexical_hits = sum(1 for r in typed_results if int(r.get("lexical_rank", 10000)) < 10000)
    semantic_hits = sum(
        1
        for r in typed_results
        if int(r.get("semantic_rank", 10000)) < 10000 and float(r.get("me5_score", 0.0)) > 0.0
    )
    lightgbm_hits = sum(1 for r in typed_results if r.get("score") is not None)

    if lexical_hits <= 0:
        return fail("component-check failed: Meilisearch lexical contribution is zero")
    if semantic_hits <= 0:
        reason = _diagnose_semantic_zero(typed_results, readyz_payload=readyz_payload)
        return fail(f"component-check failed: {reason}")
    if lightgbm_hits <= 0:
        return fail("component-check failed: LightGBM rerank contribution is zero")

    print_pretty(body)
    print(
        "component-check passed: "
        "lexical_hits="
        f"{lexical_hits} semantic_hits={semantic_hits} lightgbm_hits={lightgbm_hits} "
        f"readyz_rerank_enabled={None if readyz_payload is None else readyz_payload.get('rerank_enabled')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

