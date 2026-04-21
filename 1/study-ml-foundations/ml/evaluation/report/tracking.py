"""W&B 実験ログ管理."""

import os
from pathlib import Path

import wandb

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_wandb_dir(wandb_dir: str) -> Path:
    path = Path(wandb_dir)
    if path.is_absolute():
        resolved = path
    else:
        resolved = _REPO_ROOT / path

    # Normalize accidental nesting like ".../wandb/wandb/wandb" back to canonical depth.
    while (
        resolved.name == "wandb"
        and resolved.parent.name == "wandb"
        and resolved.parent.parent.name == "wandb"
    ):
        resolved = resolved.parent
    return resolved


def init_wandb(api_key: str, project: str, wandb_dir: str = "ml/wandb/wandb") -> None:
    """W&B を初期化する。API キーがなければ offline モード."""
    run_dir = _resolve_wandb_dir(wandb_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    os.environ["WANDB_DIR"] = str(run_dir)
    if api_key:
        os.environ["WANDB_API_KEY"] = api_key
        wandb.init(project=project, dir=str(run_dir))
    else:
        wandb.init(project=project, mode="offline", dir=str(run_dir))


def log_metrics(metrics: dict) -> None:
    """metrics を W&B に送信して run を終了する."""
    wandb.log(metrics)
    wandb.finish()
