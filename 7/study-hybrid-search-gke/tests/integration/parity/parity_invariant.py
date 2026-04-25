"""Shared invariants/helpers for parity tests.

The Python schema (`ml.data.feature_engineering.FEATURE_COLS_RANKER`) is the
canonical source of truth. Parity tests import helpers from here rather than
re-deriving the same subsets and parsers in each file.
"""

from __future__ import annotations

from pathlib import Path

from ml.data.feature_engineering import FEATURE_COLS_RANKER

REPO_ROOT = Path(__file__).resolve().parents[3]
QUERY_TIME_COLS = {"me5_score", "lexical_rank", "semantic_rank"}
PROPERTY_SIDE_COLS: list[str] = [col for col in FEATURE_COLS_RANKER if col not in QUERY_TIME_COLS]


def flat_yaml(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out
