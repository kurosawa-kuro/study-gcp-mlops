from __future__ import annotations

import sys
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "http://localhost:8000/search"


def main() -> int:
    query = urllib.parse.urlencode(
        {
            "q": "札幌",
            "layout": "2LDK",
            "price_lte": "90000",
            "pet": "true",
        }
    )
    last_error: Exception | None = None
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{URL}?{query}", timeout=10) as resp:
                print(resp.read().decode("utf-8", errors="replace"), end="")
                return 0
        except (urllib.error.URLError, OSError, ConnectionError) as exc:
            last_error = exc
            time.sleep(2)

    if last_error is not None:
        print(f"search check failed: {last_error}", file=sys.stderr)
    else:
        print("search check failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
