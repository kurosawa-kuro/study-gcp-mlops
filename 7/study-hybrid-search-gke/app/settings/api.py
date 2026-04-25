"""API settings."""

from typing import Literal

from pydantic import SecretStr

from ml.common.config import BaseAppSettings


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

    # --- Vertex AI location (used by Vector Search, Gemini, Agent Builder) ---
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

    # --- Phase 6 T3 — semantic backend (BQ VECTOR_SEARCH vs Vertex ME) ------
    semantic_backend: Literal["bq", "vertex"] = "bq"
    vertex_vector_search_index_endpoint_id: str = ""
    vertex_vector_search_deployed_index_id: str = ""

    # --- Phase 6 T6 — RAG via Gemini ----------------------------------------
    enable_rag: bool = False
    gemini_model_name: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.2

    # --- Phase 6 T1 — BQML popularity scorer --------------------------------
    bqml_popularity_enabled: bool = False
    bqml_popularity_model_fqn: str = ""

    # --- Phase 6 T7 — alternative lexical backend ----------------------------
    lexical_backend: Literal["meili", "agent_builder"] = "meili"
    vertex_agent_builder_location: str = "global"
    vertex_agent_builder_engine_id: str = ""
    vertex_agent_builder_collection_id: str = "default_collection"
    vertex_agent_builder_serving_config_id: str = "default_search"
