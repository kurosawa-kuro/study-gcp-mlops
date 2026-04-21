from __future__ import annotations

import csv
import io
import subprocess
import sys

CSV_PATH = "/app/artifacts/train/rank_train.csv"


def get_csv_from_container() -> str:
    # Returns empty string when file does not exist or command fails.
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "sh",
            "-lc",
            f"test -f {CSV_PATH} && cat {CSV_PATH}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def count_rows_and_positive(csv_text: str) -> tuple[int, int]:
    if not csv_text.strip():
        return 0, 0

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = 0
    positive = 0

    for row in reader:
        rows += 1
        try:
            if float(row.get("label", "0") or 0) > 0:
                positive += 1
        except ValueError:
            continue

    return rows, positive


def run_training() -> int:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-m", "train.trainer"],
        check=False,
    ).returncode


def main() -> int:
    csv_text = get_csv_from_container()
    rows, positive = count_rows_and_positive(csv_text)

    if rows > 0 and positive > 0:
        print(f"ops-train-fit-safe: rows={rows}, positive={positive} -> run ops-train-fit")
        return run_training()

    print(f"ops-train-fit-safe: skip ops-train-fit (rows={rows}, positive={positive})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
