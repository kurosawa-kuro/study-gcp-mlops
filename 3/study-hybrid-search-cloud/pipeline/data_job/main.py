"""Top-level pipeline entrypoint for Phase 3 data jobs.

This wrapper keeps the educational `pipeline/` surface while the current
implementation still lives in `ml.embed` and `ml.sync`.
"""

from __future__ import annotations

from ml.data.job import main


if __name__ == "__main__":
    raise SystemExit(main())
