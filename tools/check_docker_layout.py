#!/usr/bin/env python3
"""Validate Dockerfile placement rules across phases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    message: str


ROOT = Path(__file__).resolve().parents[1]


def _exists(relpath: str) -> bool:
    return (ROOT / relpath).is_file()


def _check_required() -> list[CheckResult]:
    required = [
        "2/study-hybrid-search-local/infra/run/services/search_api/Dockerfile",
        "3/study-hybrid-search-cloud/infra/run/services/search_api/Dockerfile",
        "3/study-hybrid-search-cloud/infra/run/jobs/embedding/Dockerfile",
        "3/study-hybrid-search-cloud/infra/run/jobs/training/Dockerfile",
        "4/study-hybrid-search-vertex/infra/run/jobs/embedding/Dockerfile",
        "4/study-hybrid-search-vertex/infra/run/jobs/training/Dockerfile",
        "4/study-hybrid-search-vertex/infra/run/services/encoder/Dockerfile",
        "4/study-hybrid-search-vertex/infra/run/services/reranker/Dockerfile",
        "4/study-hybrid-search-vertex/infra/run/services/search_api/Dockerfile",
        "1/study-ml-foundations/Dockerfile.trainer",
        "1/study-ml-foundations/Dockerfile.api",
    ]
    results: list[CheckResult] = []
    for rel in required:
        results.append(
            CheckResult(
                ok=_exists(rel),
                message=f"required: {rel}",
            )
        )
    return results


def _check_unexpected_suffix_dockerfiles() -> list[CheckResult]:
    allowed_suffix = {
        "1/study-ml-foundations/Dockerfile.api",
        "1/study-ml-foundations/Dockerfile.trainer",
    }
    found = [p for p in ROOT.glob("**/Dockerfile.*") if p.is_file()]
    results: list[CheckResult] = []
    for path in sorted(found):
        rel = path.relative_to(ROOT).as_posix()
        ok = rel in allowed_suffix
        results.append(
            CheckResult(
                ok=ok,
                message=f"suffix-dockerfile: {rel}",
            )
        )
    if not found:
        results.append(CheckResult(ok=True, message="suffix-dockerfile: none"))
    return results


def main() -> int:
    checks = [*_check_required(), *_check_unexpected_suffix_dockerfiles()]
    failed = [c for c in checks if not c.ok]

    print("Docker layout check")
    print("===================")
    for c in checks:
        status = "OK" if c.ok else "NG"
        print(f"[{status}] {c.message}")

    if failed:
        print(f"\nResult: FAILED ({len(failed)} issue(s))")
        return 1

    print("\nResult: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
