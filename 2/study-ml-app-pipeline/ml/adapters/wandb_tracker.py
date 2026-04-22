"""W&B tracker adapter."""

import os
from pathlib import Path

import wandb

from ml.ports.tracker import ExperimentTracker

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_wandb_dir(wandb_dir: str) -> Path:
    path = Path(wandb_dir)
    if path.is_absolute():
        return path
    return _REPO_ROOT / path


class WandbExperimentTracker(ExperimentTracker):
    def __init__(self, api_key: str, project: str, wandb_dir: str) -> None:
        self.api_key = api_key
        self.project = project
        self.wandb_dir = _resolve_wandb_dir(wandb_dir)
        self._started = False

    def start(self, run_id: str, config: dict) -> None:
        self.wandb_dir.mkdir(parents=True, exist_ok=True)
        os.environ["WANDB_DIR"] = str(self.wandb_dir)
        if self.api_key:
            os.environ["WANDB_API_KEY"] = self.api_key
            wandb.init(project=self.project, dir=str(self.wandb_dir), name=run_id, config=config)
        else:
            wandb.init(
                project=self.project,
                mode="offline",
                dir=str(self.wandb_dir),
                name=run_id,
                config=config,
            )
        self._started = True

    def log_metrics(self, metrics: dict) -> None:
        if self._started:
            wandb.log(metrics)

    def finish(self) -> None:
        if self._started:
            wandb.finish()
            self._started = False
