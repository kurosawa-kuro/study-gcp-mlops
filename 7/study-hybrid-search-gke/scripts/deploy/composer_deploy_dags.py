"""Upload pipeline/dags/*.py to the Composer DAG GCS bucket.

Phase 7 W2-4 Stage 2: Cloud Composer 環境を Terraform で立てた後、本 script が
``pipeline/dags/`` 配下の DAG ファイルを ``terraform output composer_dag_bucket``
が指す GCS bucket へ upload する (Composer scheduler が GCS を polling して
DAG を再 parse する仕組み)。

Idempotent — DAG ファイルは GCS object 上書き可なので、何度叩いても安全。

`enable_composer=false` のときは ``composer_dag_bucket`` output が空文字に
なるため early-return する (Stage 1 / Stage 2 段階での deploy_all 互換性
のため)。
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts._common import run

INFRA = Path(__file__).resolve().parents[2] / "infra" / "terraform" / "environments" / "dev"
DAGS_DIR = Path(__file__).resolve().parents[2] / "pipeline" / "dags"


def _terraform_output(name: str) -> str:
    """Read a single terraform output as a string. Empty string when unset."""
    proc = run(
        ["terraform", f"-chdir={INFRA}", "output", "-json"],
        capture=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"[error] terraform output -json failed (rc={proc.returncode})")
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[error] terraform output JSON decode failed: {exc}") from exc
    entry = payload.get(name)
    if entry is None or not isinstance(entry, dict):
        return ""
    value = entry.get("value", "")
    return str(value or "")


def _list_dag_files() -> list[Path]:
    """Return DAG .py files to upload (top-level pipeline/dags/, excluding __pycache__)."""
    return sorted(p for p in DAGS_DIR.glob("*.py") if not p.name.startswith("__pycache__"))


def main(argv: list[str] | None = None) -> int:
    del argv  # CLI args 未使用 (terraform output のみで完結)

    dag_bucket = _terraform_output("composer_dag_bucket")
    if not dag_bucket:
        print(
            "[info] composer_dag_bucket output is empty — Composer environment not provisioned "
            "(enable_composer=false?). Skipping DAG upload."
        )
        return 0

    dag_files = _list_dag_files()
    if not dag_files:
        print(f"[warn] no DAG files found under {DAGS_DIR}")
        return 0

    print(f"[info] uploading {len(dag_files)} DAG file(s) → {dag_bucket}")
    for dag_file in dag_files:
        print(f"  + {dag_file.name}")

    proc = run(
        ["gsutil", "-m", "cp", *(str(p) for p in dag_files), dag_bucket],
        capture=False,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"[error] gsutil cp DAGs failed (rc={proc.returncode})")

    print(f"[info] composer-deploy-dags complete ({len(dag_files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
