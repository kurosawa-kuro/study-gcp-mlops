"""API settings."""

from __future__ import annotations

from functools import cached_property

from pydantic import BaseModel, SecretStr

from ml.common.config import BaseAppSettings


class FeatureFlags(BaseModel):
    enable_search: bool
    enable_rerank: bool
    enable_rag: bool


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


class RagSettings(BaseModel):
    enabled: bool
    model_name: str
    temperature: float
    max_output_tokens: int


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

    # --- Vertex AI location (used by Gemini RAG / Model Registry / Pipelines) -
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

    # --- Phase 6 T6 — RAG via Gemini ----------------------------------------
    enable_rag: bool = False
    # Phase 7 Run 2 検証で `gemini-1.5-flash` が ``asia-northeast1`` で 404 になる
    # ことを確認 (deprecated/region 不在)。current GA model に切替え済。
    gemini_model_name: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.2
    # Gemini 2.5-flash は内部 reasoning に "thinking tokens" を消費する
    # (Phase 7 Run 2 で 509 thoughts / 512 budget で finish_reason=MAX_TOKENS
    # になる事象を確認)。512 では実出力が出ないので 2048 を default にし、
    # 旧モデル運用時は ``GEMINI_MAX_OUTPUT_TOKENS=512`` で env override 可能。
    gemini_max_output_tokens: int = 2048

    # --- Phase 6 T1 — BQML popularity scorer --------------------------------
    bqml_popularity_enabled: bool = False
    bqml_popularity_model_fqn: str = ""

    @cached_property
    def feature_flags(self) -> FeatureFlags:
        return FeatureFlags(
            enable_search=self.enable_search,
            enable_rerank=self.enable_rerank,
            enable_rag=self.enable_rag,
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
    def rag(self) -> RagSettings:
        return RagSettings(
            enabled=self.enable_rag,
            model_name=self.gemini_model_name,
            temperature=self.gemini_temperature,
            max_output_tokens=self.gemini_max_output_tokens,
        )

    @cached_property
    def popularity(self) -> PopularitySettings:
        return PopularitySettings(
            enabled=self.bqml_popularity_enabled,
            model_fqn=self.bqml_popularity_model_fqn,
        )
