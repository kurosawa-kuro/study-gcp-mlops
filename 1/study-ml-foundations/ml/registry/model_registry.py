from ml.data.loaders.repository import PostgresRepository


class ModelRegistry:
    def __init__(self, dsn: str) -> None:
        self._repo = PostgresRepository(dsn)

    def register_run(self, run_id: str, metrics: dict) -> None:
        self._repo.save_run(run_id, metrics)

    def list_runs(self):
        return self._repo.fetch_runs()
