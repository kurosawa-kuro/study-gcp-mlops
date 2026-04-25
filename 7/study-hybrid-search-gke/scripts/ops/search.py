"""Smoke-test the deployed /search endpoint. Phase 4 (rerank-free) returns
results where final_rank == lexical_rank and score is null.
Override QUERY / TOP_K / MAX_RENT via env vars.
"""

from __future__ import annotations

import os

from scripts._common import fail, http_json, print_pretty, resolve_api_target


def main() -> int:
    query = os.environ.get("QUERY", "赤羽駅徒歩10分 ペット可")
    top_k = int(os.environ.get("TOP_K", "20"))
    max_rent = int(os.environ.get("MAX_RENT", "150000"))

    try:
        target = resolve_api_target()
    except Exception as exc:
        return fail(f"search config error: {exc}")
    payload = {"query": query, "filters": {"max_rent": max_rent}, "top_k": top_k}
    status, body = http_json("POST", f"{target.url}/search", token=target.token, payload=payload)
    if status != 200:
        return fail(f"search returned HTTP {status}: {body}")
    print_pretty(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
