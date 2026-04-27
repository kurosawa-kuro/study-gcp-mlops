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


class KServeSettings(BaseModel):
    encoder_url: str
    reranker_url: str
    reranker_explain_url: str
    predict_timeout_seconds: float
    search_cache_ttl_seconds: int
    search_cache_maxsize: int


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
    meili_service: str = "meili-search"
    meili_index_name: str = "properties"
    meili_api_key: str = ""
    meili_master_key: SecretStr = SecretStr("")  # Secret Manager: meili-master-key
    meili_require_identity_token: bool = True
    meili_impersonate_service_account: str = ""
    meili_token_audience: str = ""

    # --- Vertex AI location (used by Model Registry / Pipelines) -------------
    vertex_location: str = "asia-northeast1"

    # --- KServe inference endpoints (cluster-local HTTP) ----------------------
    kserve_encoder_url: str = ""
    kserve_reranker_url: str = ""
    kserve_reranker_explain_url: str = ""
    kserve_predict_timeout_seconds: float = 30.0

    # --- Phase 6 /search rerank (optional bolt-on) ---------------------------
    enable_rerank: bool = False
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
    def kserve(self) -> KServeSettings:
        return KServeSettings(
            encoder_url=self.kserve_encoder_url,
            reranker_url=self.kserve_reranker_url,
            reranker_explain_url=self.kserve_reranker_explain_url,
            predict_timeout_seconds=self.kserve_predict_timeout_seconds,
            search_cache_ttl_seconds=self.search_cache_ttl_seconds,
            search_cache_maxsize=self.search_cache_maxsize,
        )

    @cached_property
    def popularity(self) -> PopularitySettings:
        return PopularitySettings(
            enabled=self.bqml_popularity_enabled,
            model_fqn=self.bqml_popularity_model_fqn,
        )
