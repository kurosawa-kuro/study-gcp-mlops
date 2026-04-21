"""pipeline パッケージのテスト（config, repository）."""

from ml.data.loaders.config import Settings
from ml.data.loaders.repository import PostgresRepository


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.data_source == "postgres"
        assert s.postgres_db == "mlpipeline"
        assert s.postgres_user == "admin"
        assert s.postgres_port == 5432
        assert s.model_dir == "ml/registry/artifacts"

    def test_postgres_dsn(self):
        s = Settings(
            postgres_host="db",
            postgres_port=5433,
            postgres_db="foo",
            postgres_user="u",
            postgres_password="p",
        )
        assert s.postgres_dsn == "postgresql+psycopg://u:p@db:5433/foo"


class TestPostgresRepository:
    def test_fetch_train(self, sample_db):
        repo = PostgresRepository(sample_db)
        df = repo.fetch_train()
        assert len(df) == 80
        assert "Price" in df.columns

    def test_fetch_test(self, sample_db):
        repo = PostgresRepository(sample_db)
        df = repo.fetch_test()
        assert len(df) == 20
        assert "Price" in df.columns

    def test_save_and_fetch_runs(self, sample_db):
        repo = PostgresRepository(sample_db)
        repo.save_run("run_001", {"rmse": 0.5, "r2": 0.8})
        repo.save_run("run_002", {"rmse": 0.4, "r2": 0.85})

        runs = repo.fetch_runs()
        assert len(runs) == 2
        assert runs.iloc[0]["run_id"] == "run_002"  # 新しい順
        assert runs.iloc[1]["run_id"] == "run_001"

    def test_save_run_upsert(self, sample_db):
        repo = PostgresRepository(sample_db)
        repo.save_run("run_001", {"rmse": 0.5, "r2": 0.8})
        repo.save_run("run_001", {"rmse": 0.4, "r2": 0.85})  # 同じ run_id で上書き

        runs = repo.fetch_runs()
        assert len(runs) == 1
        assert runs.iloc[0]["rmse"] == 0.4
