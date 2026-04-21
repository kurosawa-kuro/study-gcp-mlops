#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import compose, project_root, run, step


def main() -> None:
    root = project_root()
    step("Cleaning")

    compose(["down", "--remove-orphans", "--volumes"], check=False)

    models_dir = root / "ml" / "registry" / "artifacts"
    wandb_dir = root / "ml" / "wandb" / "wandb"
    if models_dir.exists() or wandb_dir.exists():
        run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{models_dir}:/work/models",
                "-v",
                f"{wandb_dir}:/work/wandb",
                "alpine",
                "sh",
                "-c",
                "rm -rf /work/models/* /work/wandb/*",
            ],
            check=False,
        )

    print("Done.")


if __name__ == "__main__":
    main()
