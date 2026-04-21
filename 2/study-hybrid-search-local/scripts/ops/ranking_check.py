from __future__ import annotations

import json
import urllib.parse
import urllib.request

URL = "http://localhost:8000/search"


def main() -> int:
    query = urllib.parse.urlencode(
        {
            "q": "札幌 ペット可 2LDK",
            "layout": "2LDK",
            "price_lte": "90000",
            "pet": "true",
            "user_id": "1",
        }
    )
    with urllib.request.urlopen(f"{URL}?{query}", timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    first = (data.get("items") or [{}])[0]
    print("search_log_id=", data.get("search_log_id"))
    print("first_item_id=", first.get("id"))
    print("first_item_me5_score=", first.get("me5_score"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
