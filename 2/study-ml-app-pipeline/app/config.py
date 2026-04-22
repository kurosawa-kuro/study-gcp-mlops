"""API 設定管理."""

from ml.common.config.base import BaseAppSettings


class Settings(BaseAppSettings):
    model_path: str = "ml/registry/artifacts/latest/model.lgb"
