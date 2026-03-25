#!/usr/bin/env python3
"""全体冪等デプロイ: batch + API デプロイ → batch実行"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: str) -> None:
    print(f"\n==> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT)
    if result.returncode != 0:
        print(f"エラー: '{cmd}' が失敗しました (code={result.returncode})")
        sys.exit(result.returncode)


def main() -> None:
    run("make deploy")
    run("make batch-run")
    print("\n==> 完了")


if __name__ == "__main__":
    main()
