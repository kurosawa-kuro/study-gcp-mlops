"""API settings."""

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

    # --- KServe inference endpoints (cluster-local HTTP) ----------------------
    # In-cluster DNS: http://<service>.<namespace>.svc.cluster.local
    # NetworkPolicy restricts callers to search-api Pod only, so no additional
    # auth is required on the encoder / reranker side.
    kserve_encoder_url: str = ""
    kserve_reranker_url: str = ""
    kserve_predict_timeout_seconds: float = 30.0

    # --- Phase 6 /search rerank (optional bolt-on) ---------------------------
    # When False, /search returns candidates in lexical_rank order with score=None.
    # When True, the API calls the configured KServe reranker endpoint.
    enable_rerank: bool = False
    search_cache_ttl_seconds: int = 120
    search_cache_maxsize: int = 2048
