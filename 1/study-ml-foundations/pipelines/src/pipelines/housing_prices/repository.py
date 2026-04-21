"""データアクセス層 — Repository パターン."""

from datetime import datetime
from typing import Protocol

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class TrainingDataRepository(Protocol):
    def fetch_train(self) -> pd.DataFrame: ...
    def fetch_test(self) -> pd.DataFrame: ...
    def save_run(self, run_id: str, metrics: dict) -> None: ...
    def fetch_runs(self) -> pd.DataFrame: ...


class PostgresRepository:
    _ALLOWED_TABLES = {"training_data", "test_data"}

    def __init__(self, dsn: str) -> None:
        self.engine: Engine = create_engine(dsn, future=True)
        self._ensure_runs_table()

    def _ensure_runs_table(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS model_runs (
                    run_id     TEXT PRIMARY KEY,
                    rmse       DOUBLE PRECISION NOT NULL,
                    r2         DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
            """))

    def _query(self, table: str) -> pd.DataFrame:
        if table not in self._ALLOWED_TABLES:
            raise ValueError(f"Invalid table: {table}")
        with self.engine.connect() as conn:
            return pd.read_sql(text(f"SELECT * FROM {table}"), conn)

    def fetch_train(self) -> pd.DataFrame:
        return self._query("training_data")

    def fetch_test(self) -> pd.DataFrame:
        return self._query("test_data")

    def save_run(self, run_id: str, metrics: dict) -> None:
        """学習結果を model_runs テーブルに記録する (upsert)."""
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO model_runs (run_id, rmse, r2, created_at)
                    VALUES (:run_id, :rmse, :r2, :created_at)
                    ON CONFLICT (run_id) DO UPDATE SET
                        rmse = EXCLUDED.rmse,
                        r2 = EXCLUDED.r2,
                        created_at = EXCLUDED.created_at
                """),
                {
                    "run_id": run_id,
                    "rmse": metrics["rmse"],
                    "r2": metrics["r2"],
                    "created_at": datetime.now(),
                },
            )

    def fetch_runs(self) -> pd.DataFrame:
        """model_runs テーブルの全レコードを取得する."""
        with self.engine.connect() as conn:
            return pd.read_sql(
                text("SELECT * FROM model_runs ORDER BY created_at DESC"), conn
            )


def get_repository(settings) -> TrainingDataRepository:
    if settings.data_source == "postgres":
        return PostgresRepository(settings.postgres_dsn)
    raise ValueError(f"Unsupported data_source: {settings.data_source}")
