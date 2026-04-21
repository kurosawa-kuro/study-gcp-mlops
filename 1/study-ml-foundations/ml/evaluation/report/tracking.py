"""W&B 実験ログ管理."""

import os
from pathlib import Path

import wandb

WANDB_DIR = Path(__file__).resolve().parents[2] / "wandb"


def init_wandb(api_key: str, project: str) -> None:
    """W&B を初期化する。API キーがなければ offline モード."""
    WANDB_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["WANDB_DIR"] = str(WANDB_DIR)
    if api_key:
        os.environ["WANDB_API_KEY"] = api_key
        wandb.init(project=project, dir=str(WANDB_DIR))
    else:
        wandb.init(project=project, mode="offline", dir=str(WANDB_DIR))


def log_metrics(metrics: dict) -> None:
    """metrics を W&B に送信して run を終了する."""
    wandb.log(metrics)
    wandb.finish()
