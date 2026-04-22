from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

SEARCH_URL = "http://localhost:8000/search"
FEEDBACK_URL = "http://localhost:8000/feedback"


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
    with urllib.request.urlopen(f"{SEARCH_URL}?{query}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_feedback(search_log_id: int) -> dict:
    payload = json.dumps(
        {
            "user_id": 1,
            "property_id": 1,
            "action": "click",
            "search_log_id": search_log_id,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        FEEDBACK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    for _ in range(5):
        data = search_once()
        search_log_id = data.get("search_log_id")
        if search_log_id:
            out = post_feedback(int(search_log_id))
            print(json.dumps(out, ensure_ascii=False), end="")
            return 0
        time.sleep(2)

    print("phase2-feedback-check failed: search_log_id not found", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
