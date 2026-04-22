from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


def _request(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body


def main() -> int:
    base = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
    q = os.environ.get("QUERY", "札幌")
    limit = int(os.environ.get("TOP_K", "20"))
    layout = os.environ.get("LAYOUT", "2LDK")
    price_lte = os.environ.get("PRICE_LTE", "90000")
    pet = os.environ.get("PET", "true")
    params = urllib.parse.urlencode(
        {
            "q": q,
            "layout": layout,
            "price_lte": price_lte,
            "pet": pet,
            "limit": str(limit),
        }
    )
    status, body = _request(f"{base}/search?{params}")
    if status != 200:
        print(f"component-check failed: /search returned HTTP {status}: {body}")
        return 1
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        print(f"component-check failed: /search returned non-JSON body: {body}")
        return 1
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        print("component-check failed: /search returned empty items")
        return 1

    meili_hits = len(items)  # local v3 candidates originate from Meilisearch.
    me5_hits = sum(
        1 for item in items if isinstance(item, dict) and float(item.get("me5_score", 0.0)) > 0.0
    )
    lightgbm_hits = sum(
        1 for item in items if isinstance(item, dict) and item.get("lgbm_score") is not None
    )

    if meili_hits <= 0:
        print("component-check failed: Meilisearch lexical contribution is zero")
        return 1
    if me5_hits <= 0:
        print("component-check failed: ME5 semantic contribution is zero")
        return 1
    if lightgbm_hits <= 0:
        print("component-check failed: LightGBM rerank contribution is zero")
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(
        "component-check passed: "
        f"lexical_hits={meili_hits} semantic_hits={me5_hits} lightgbm_hits={lightgbm_hits}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
