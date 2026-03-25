#!/usr/bin/env python3
"""リセット: GCPリソース全削除 → ローカル状態クリーン"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TF_DIR = ROOT / "terraform"

CLEANUP_DIRS = [".terraform"]
CLEANUP_FILES = [".terraform.lock.hcl", "terraform.tfstate", "terraform.tfstate.backup"]

ML_DIR_NAME = "src/ml"
ML_CLEANUP_DIRS = ["outputs", "mlruns", "mlartifacts"]
ML_CLEANUP_FILES = ["mlflow.db"]


def run(cmd: str, allow_fail: bool = False) -> None:
    print(f"\n==> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT)
    if result.returncode != 0 and not allow_fail:
        print(f"エラー: '{cmd}' が失敗しました (code={result.returncode})")
        sys.exit(result.returncode)


def clean_terraform_local() -> None:
    print("\n==> Terraformローカル状態クリーン")
    for name in CLEANUP_DIRS:
        target = TF_DIR / name
        if target.is_dir():
            shutil.rmtree(target)
            print(f"  削除: {target}")

    for name in CLEANUP_FILES:
        target = TF_DIR / name
        if target.is_file():
            target.unlink()
            print(f"  削除: {target}")


def clean_ml_local() -> None:
    ml_dir = ROOT / ML_DIR_NAME
    print("\n==> ML成果物クリーン")
    for name in ML_CLEANUP_DIRS:
        target = ml_dir / name
        if target.is_dir():
            shutil.rmtree(target)
            print(f"  削除: {target}")

    for name in ML_CLEANUP_FILES:
        target = ml_dir / name
        if target.is_file():
            target.unlink()
            print(f"  削除: {target}")


def main() -> None:
    run("make tf-destroy")
    clean_terraform_local()
    clean_ml_local()

    # Makefileから IMAGE_BASE を取得してイメージ削除
    run("docker images --format '{{.Repository}}:{{.Tag}}' "
        "| grep mlops-dev-a/mlops-dev-a-docker "
        "| xargs -r docker rmi", allow_fail=True)

    print("\n==> リセット完了。make deploy で再構築できます。")


if __name__ == "__main__":
    main()
