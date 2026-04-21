"""API 設定管理."""

from common.config import BaseAppSettings


class Settings(BaseAppSettings):
    model_path: str = "models/latest/model.lgb"
