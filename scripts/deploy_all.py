#!/usr/bin/env python3
"""全体冪等デプロイ: batch + API デプロイ → batch実行"""

from core import run


def main() -> None:
    run("make deploy")
    run("make batch-run")
    print("\n==> 完了")


if __name__ == "__main__":
    main()
