"""AST-based layer boundary checker (MLOps skeleton edition).

Walks every Port / pure-logic module listed in `RULES` and reports any
forbidden import (concrete adapter, GCP SDK, W&B, LightGBM where
inapplicable). Each file is inspected at *every* `Import` / `ImportFrom`
node — top-level AND inside functions — so lazy imports cannot smuggle a
banned dependency back in.

Two consumers share the canonical ruleset declared here:

- `tests/unit/arch/test_import_boundaries.py` imports `RULES`, `UNIVERSAL_BANS`,
  and `find_violations()` so pytest cases stay aligned with this script.
- `make check-layers` runs `python -m scripts.ci.layers` for ad-hoc
  inspection outside pytest. Exit code 0 = clean, 1 = violations found,
  with `<rel_path>:<line>` references for every offending import.

To add a rule: extend `RULES` below. Both the CLI and the pytest cases
pick the change up automatically.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every Port / pure-logic file is disallowed from importing these at all.
UNIVERSAL_BANS: frozenset[str] = frozenset()

# Concrete GCP / runtime integrations that must not leak into pure-logic
# modules (protocols, pure functions, schemas).
ADAPTER_BANS: frozenset[str] = frozenset({"google.cloud"})

RULES: dict[str, frozenset[str]] = {
    # --- ml.common (pure utilities) ---
    "ml/common/config/base.py": ADAPTER_BANS | frozenset({"lightgbm"}),
    "ml/common/logging/structured_logging.py": ADAPTER_BANS
    | frozenset({"lightgbm", "pandas", "numpy"}),
    "ml/common/utils/run_id.py": ADAPTER_BANS | frozenset({"lightgbm", "pandas", "numpy"}),
    # --- ml.data.feature_engineering / ml.evaluation (pure logic) ---
    "ml/data/feature_engineering/schema.py": ADAPTER_BANS
    | frozenset({"lightgbm", "pandas", "numpy"}),
    "ml/data/feature_engineering/ranker_features.py": ADAPTER_BANS | frozenset({"lightgbm"}),
    "ml/evaluation/metrics/ranking.py": ADAPTER_BANS | frozenset({"lightgbm", "pandas"}),
    "ml/evaluation/metrics/label_gain.py": ADAPTER_BANS
    | frozenset({"lightgbm", "pandas", "numpy"}),
    # --- app/ — Port + pure-logic layer ---
    "app/services/protocols/publisher.py": ADAPTER_BANS,
    "app/services/protocols/retrain_queries.py": ADAPTER_BANS,
    "app/services/protocols/cache_store.py": ADAPTER_BANS,
    "app/services/protocols/lexical_search.py": ADAPTER_BANS,
    "app/services/protocols/candidate_retriever.py": ADAPTER_BANS | frozenset({"lightgbm"}),
    "app/services/protocols/encoder_client.py": ADAPTER_BANS,
    "app/services/protocols/reranker_client.py": ADAPTER_BANS,
    "app/services/retrain_policy.py": ADAPTER_BANS,
    "app/services/ranking.py": ADAPTER_BANS | frozenset({"sentence_transformers"}),
    "app/schemas/search.py": ADAPTER_BANS | frozenset({"lightgbm", "numpy"}),
    "app/api/middleware/request_logging.py": ADAPTER_BANS,
    "app/services/config.py": ADAPTER_BANS | frozenset({"lightgbm"}),
}


@dataclass(frozen=True)
class Violation:
    """One forbidden import in one file."""

    rel_path: str
    line: int
    imported: str
    banned_prefix: str

    def __str__(self) -> str:
        return (
            f"{self.rel_path}:{self.line}  import {self.imported!r} "
            f"hits banned prefix {self.banned_prefix!r}"
        )


def _imports_with_lines(path: Path) -> list[tuple[int, str]]:
    """Every imported module name + the source line where it appears."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found


def _matches(imported: str, banned: str) -> bool:
    """Prefix match: imported equals `banned` itself or is one of its submodules."""
    return imported == banned or imported.startswith(banned + ".")


def find_violations(rel_path: str) -> list[Violation]:
    """Return every `(line, imported, banned_prefix)` violation in the given file."""
    path = REPO_ROOT / rel_path
    if not path.exists():
        return [Violation(rel_path, 0, "<missing source file>", "")]

    bans = UNIVERSAL_BANS | RULES[rel_path]
    found: list[Violation] = []
    for line, imp in _imports_with_lines(path):
        for banned in bans:
            if _matches(imp, banned):
                found.append(Violation(rel_path, line, imp, banned))
    return sorted(found, key=lambda v: (v.rel_path, v.line, v.imported))


def main() -> int:
    total = 0
    for rel_path in sorted(RULES):
        for v in find_violations(rel_path):
            print(v)
            total += 1
    if total == 0:
        print(f"check-layers: OK ({len(RULES)} files clean)")
        return 0
    print(f"check-layers: FAIL ({total} violations across {len(RULES)} files)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
