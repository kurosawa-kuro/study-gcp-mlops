"""POST /jobs/check-retrain on search-api with an OIDC token. The endpoint
inspects training_runs / feedback freshness and returns whether the
retrain-trigger Pub/Sub topic should fire (used by Cloud Scheduler daily).
"""

from __future__ import annotations

from scripts._common import fail, print_pretty, resolve_api_target


def main() -> int:
    try:
        target = resolve_api_target()
    except Exception as exc:
        return fail(f"check-retrain config error: {exc}")
    status, body = target.call("POST", "/jobs/check-retrain")
    if status != 200:
        return fail(f"check-retrain returned HTTP {status}: {body}")
    print_pretty(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
