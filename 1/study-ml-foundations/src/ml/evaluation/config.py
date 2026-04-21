"""評価・実験ログ設定管理."""

from common.config import BaseAppSettings


class EvalSettings(BaseAppSettings):
    wandb_api_key: str = ""
    wandb_project: str = "california-housing"
