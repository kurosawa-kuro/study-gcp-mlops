from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

SEARCH_URL = "http://localhost:8000/search"
FEEDBACK_URL = "http://localhost:8000/feedback"
ACTIONS = ("click", "favorite", "inquiry")


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


def post_feedback(property_id: int, search_log_id: int, action: str) -> None:
    payload = json.dumps(
        {
            "user_id": 1,
            "property_id": property_id,
            "action": action,
            "search_log_id": search_log_id,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        FEEDBACK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10):
        return


def main() -> int:
    posted = 0

    for action in ACTIONS:
        for _ in range(10):
            data = search_once()
            log_id = data.get("search_log_id")
            items = data.get("items") or []
            prop_id = items[0].get("id") if items else None

            if log_id and prop_id:
                post_feedback(int(prop_id), int(log_id), action)
                posted += 1
                break

            time.sleep(1)

    print(f"phase5-label-seed completed: posted={posted}")
    if posted == 0:
        print("phase5-label-seed failed: no feedback posted", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
