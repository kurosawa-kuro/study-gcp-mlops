"""DI container."""

from dataclasses import dataclass

from ml.adapters.filesystem_model_store import FilesystemModelStore
from ml.adapters.predictor import ModelStorePredictor
from ml.adapters.postgres_dataset import PostgresDatasetAdapter
from ml.ports.dataset import DatasetReader
from ml.ports.model_store import ModelStore
from ml.ports.predictor import Predictor


@dataclass(frozen=True)
class Container:
    dataset: DatasetReader
    model_store: ModelStore
    predictor: Predictor


def build_container(settings) -> Container:
    dataset = PostgresDatasetAdapter(settings.postgres_dsn)
    model_store = FilesystemModelStore(settings.model_dir)
    predictor = ModelStorePredictor(model_store)
    return Container(dataset=dataset, model_store=model_store, predictor=predictor)
