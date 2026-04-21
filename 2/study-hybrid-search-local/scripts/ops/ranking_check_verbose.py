from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

URL = "http://localhost:8000/search"


def search_once() -> dict:
    query = urllib.parse.urlencode(
        {
            "q": "札幌",
            "layout": "2LDK",
            "price_lte": "90000",
            "pet": "true",
            "user_id": "1",
        }
    )
    with urllib.request.urlopen(f"{URL}?{query}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    for _ in range(10):
        try:
            data = search_once()
            first = (data.get("items") or [{}])[0]
            print("search_log_id=", data.get("search_log_id"))
            print("first_item_id=", first.get("id"))
            print("first_item_lgbm_score=", first.get("lgbm_score"))
            print("first_item_me5_score=", first.get("me5_score"))
            return 0
        except Exception:
            time.sleep(1)

    print("phase5-search-check failed: API did not return valid JSON", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
