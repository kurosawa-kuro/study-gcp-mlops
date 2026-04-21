#!/usr/bin/env python3
from __future__ import annotations

from core import compose, project_root, run, step


def main() -> None:
    root = project_root()
    step("Cleaning")

    compose(["down", "--remove-orphans", "--volumes"], check=False)

    models_dir = root / "models"
    artifacts_dir = root / "artifacts"
    wandb_dir = artifacts_dir / "wandb"
    if models_dir.exists() or wandb_dir.exists():
        run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{models_dir}:/work/models",
                "-v",
                f"{artifacts_dir}:/work/artifacts",
                "alpine",
                "sh",
                "-c",
                "rm -rf /work/models/* /work/artifacts/wandb",
            ],
            check=False,
        )

    print("Done.")


if __name__ == "__main__":
    main()
