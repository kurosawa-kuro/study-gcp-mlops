"""Embedding-job settings (lightweight subset of BaseAppSettings)."""

from common.config import BaseAppSettings


class EmbedSettings(BaseAppSettings):
    """Env-driven settings required by the embedding pipeline / encoder CPR.

    Intentionally thin — ME5 hyperparameters live on :class:`E5Encoder` and
    LightGBM knobs belong to :mod:`train.config`, not here.
    """
