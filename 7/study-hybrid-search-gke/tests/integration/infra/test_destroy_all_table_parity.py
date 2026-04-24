"""Parity: ``scripts.setup.destroy_all.PROTECTED_TABLE_TARGETS`` ↔ data/main.tf.

``destroy-all`` must flip ``deletion_protection=false`` on every protected BQ
table *before* running ``terraform destroy``; otherwise destroy fails with
``Error: cannot destroy table ... without setting deletion_protection=false``.
The list in destroy_all.py is hand-maintained. This test catches drift when a
new protected table is added to ``infra/terraform/modules/data/main.tf`` but
not mirrored into PROTECTED_TABLE_TARGETS.

Phase 6 Run 2 already took a hit here (``properties_enriched`` +
``ranking_log_hourly_ctr`` slipped through and broke destroy-all). This test
prevents that class of drift going forward.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_TF = REPO_ROOT / "infra" / "terraform" / "modules" / "data" / "main.tf"

_BQ_TABLE_RE = re.compile(r'resource\s+"google_bigquery_table"\s+"([^"]+)"')
_PROTECTED_RE = re.compile(r"deletion_protection\s*=\s*(?:true|var\.enable_deletion_protection)")


def _terraform_protected_tables() -> set[str]:
    """Every ``google_bigquery_table`` resource whose body mentions
    ``deletion_protection`` (either literally true or bound to the
    ``enable_deletion_protection`` var)."""
    text = DATA_TF.read_text(encoding="utf-8")
    protected: set[str] = set()
    # Split into resource blocks so we can match block-locally.
    # A simple split works because resource blocks don't nest.
    blocks = re.split(r'(?=resource\s+"[^"]+"\s+"[^"]+"\s*\{)', text)
    for block in blocks:
        m = _BQ_TABLE_RE.match(block)
        if not m:
            continue
        if _PROTECTED_RE.search(block):
            protected.add(m.group(1))
    return protected


def _destroy_all_targets() -> set[str]:
    from scripts.setup.destroy_all import PROTECTED_TABLE_TARGETS

    prefix = "module.data.google_bigquery_table."
    names: set[str] = set()
    for target in PROTECTED_TABLE_TARGETS:
        assert target.startswith(prefix), (
            f"PROTECTED_TABLE_TARGETS entry {target!r} must start with {prefix!r}; "
            "destroy_all passes these as -target=<address> to terraform apply."
        )
        names.add(target[len(prefix) :])
    return names


def test_every_protected_table_is_in_destroy_all_targets() -> None:
    """Every BQ table declared with ``deletion_protection`` in data/main.tf
    must be listed in ``PROTECTED_TABLE_TARGETS``; otherwise destroy-all
    fails mid-flight when terraform destroy hits the unprotected table.
    """
    tf_tables = _terraform_protected_tables()
    destroy_tables = _destroy_all_targets()
    missing = tf_tables - destroy_tables
    assert not missing, (
        f"New protected BQ table(s) in data/main.tf not mirrored into "
        f"scripts.setup.destroy_all.PROTECTED_TABLE_TARGETS: {sorted(missing)}. "
        "Add them (prefixed with `module.data.google_bigquery_table.`) before "
        "merging, or make destroy-all will fail during `terraform destroy`."
    )


def test_destroy_all_targets_do_not_reference_removed_tables() -> None:
    """Opposite drift: a table removed from data/main.tf must not linger in
    PROTECTED_TABLE_TARGETS — otherwise the state-flip apply will fail with
    ``resource not in state``.
    """
    tf_tables = _terraform_protected_tables()
    destroy_tables = _destroy_all_targets()
    stale = destroy_tables - tf_tables
    assert not stale, (
        f"PROTECTED_TABLE_TARGETS references tables that no longer exist in "
        f"data/main.tf: {sorted(stale)}. Remove them from destroy_all.py."
    )


def test_ten_tables_baseline() -> None:
    """Sanity: as of Phase 6 Run 2 we have 10 protected tables. This baseline
    is advisory (not a hard contract) — if the count changes intentionally,
    update this number so the next reader sees the canonical state.
    """
    destroy_tables = _destroy_all_targets()
    assert len(destroy_tables) == 10, (
        f"Expected 10 protected BQ tables (Phase 6 Run 2 baseline), got "
        f"{len(destroy_tables)}: {sorted(destroy_tables)}. "
        "If the count changed intentionally, bump this baseline."
    )
