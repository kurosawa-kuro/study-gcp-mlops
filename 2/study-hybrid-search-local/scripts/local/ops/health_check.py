from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

URL = "http://localhost:8000/health"


def main() -> int:
    for _ in range(10):
        try:
            with urllib.request.urlopen(URL, timeout=5) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status == 200:
                    print(body, end="")
                    return 0
        except (urllib.error.URLError, OSError, ConnectionError):
            pass
        time.sleep(2)

    print("health check failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
