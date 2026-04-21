#!/usr/bin/env python3
from __future__ import annotations

import sys

from core import python_bin, run, step


def main() -> None:
    step("Running tests")
    run([python_bin(), "-m", "pytest", "tests/", "-v", *sys.argv[1:]])


if __name__ == "__main__":
    main()
