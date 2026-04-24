"""Embedding job settings.

Inherits from :class:`common.config.BaseAppSettings` so ``project_id`` /
``bq_dataset_feature_mart`` / ``gcs_models_bucket`` resolve identically to
the training job. The embedding runner itself does not need LightGBM
hyperparameters; those live in ``train.config.TrainSettings`` on the train
side.
"""

from common.config import BaseAppSettings


class EmbedSettings(BaseAppSettings):
    pass
