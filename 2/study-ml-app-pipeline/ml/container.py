"""DI container."""

from dataclasses import dataclass

from ml.adapters.filesystem_model_store import FilesystemModelStore
from ml.adapters.postgres_dataset import PostgresDatasetAdapter
from ml.adapters.wandb_tracker import WandbExperimentTracker
from ml.ports.dataset import DatasetReader
from ml.ports.model_store import ModelStore
from ml.ports.tracker import ExperimentTracker


@dataclass(frozen=True)
class Container:
    dataset: DatasetReader
    model_store: ModelStore
    tracker: ExperimentTracker


def build_container(settings) -> Container:
    dataset = PostgresDatasetAdapter(settings.postgres_dsn)
    model_store = FilesystemModelStore(settings.model_dir)
    tracker = WandbExperimentTracker(
        api_key=settings.wandb_api_key,
        project=settings.wandb_project,
        wandb_dir=settings.wandb_dir,
    )
    return Container(dataset=dataset, model_store=model_store, tracker=tracker)
