"""パイプライン設定管理."""

from share.config import BaseAppSettings


class Settings(BaseAppSettings):
    # データソース
    data_source: str = "postgres"

    # PostgreSQL 接続情報
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "mlpipeline"
    postgres_user: str = "admin"
    postgres_password: str = "password"

    # モデル出力先
    model_dir: str = "models"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
