"""API settings."""

from __future__ import annotations

from functools import cached_property

from pydantic import BaseModel, SecretStr

from ml.common.config import BaseAppSettings


class FeatureFlags(BaseModel):
    enable_search: bool
    enable_rerank: bool


class MessagingSettings(BaseModel):
    ranking_log_topic: str
    feedback_topic: str
    retrain_topic: str


class PopularitySettings(BaseModel):
    enabled: bool
    model_fqn: str


class ApiSettings(BaseAppSettings):
    # --- /search + /feedback -------------------------------------------------
    enable_search: bool = False
    ranking_log_topic: str = "ranking-log"
    feedback_topic: str = "search-feedback"
    retrain_topic: str = "retrain-trigger"
    bq_table_property_embeddings: str = "property_embeddings"
    bq_table_property_features_daily: str = "property_features_daily"
    bq_table_properties_cleaned: str = "properties_cleaned"
    meili_base_url: str = ""
    meili_index_name: str = "properties"
    meili_api_key: str = ""
    meili_master_key: SecretStr = SecretStr("")  # Secret Manager: meili-master-key
    meili_require_identity_token: bool = True

    # --- Vertex AI location (used by Endpoints / Model Registry / Pipelines) -
    vertex_location: str = "asia-northeast1"

    # --- Vertex Endpoint inference targets -----------------------------------
    vertex_encoder_endpoint_id: str = ""
    vertex_predict_timeout_seconds: float = 30.0

    # --- Phase 6 /search rerank (optional bolt-on) ---------------------------
    enable_rerank: bool = False
    vertex_reranker_endpoint_id: str = ""
    search_cache_ttl_seconds: int = 120
    search_cache_maxsize: int = 2048

    # --- Phase 6 T1 — BQML popularity scorer --------------------------------
    bqml_popularity_enabled: bool = False
    bqml_popularity_model_fqn: str = ""

    @cached_property
    def feature_flags(self) -> FeatureFlags:
        return FeatureFlags(
            enable_search=self.enable_search,
            enable_rerank=self.enable_rerank,
        )

    @cached_property
    def messaging(self) -> MessagingSettings:
        return MessagingSettings(
            ranking_log_topic=self.ranking_log_topic,
            feedback_topic=self.feedback_topic,
            retrain_topic=self.retrain_topic,
        )

    @cached_property
    def popularity(self) -> PopularitySettings:
        return PopularitySettings(
            enabled=self.bqml_popularity_enabled,
            model_fqn=self.bqml_popularity_model_fqn,
        )
