"""API 設定管理."""

from ml.common.config.base import BaseAppSettings


class Settings(BaseAppSettings):
    model_path: str = "models/latest/model.lgb"
