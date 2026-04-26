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
    meili_require_identity_token: bool = True
    # Secret Manager 経由で Cloud Run に注入 (--set-secrets MEILI_MASTER_KEY=meili-master-key:latest)
    # ローカル開発時は env/secret/credential.yaml の meili_master_key キーまたは環境変数で供給する。
    meili_master_key: SecretStr = SecretStr("")
    vertex_location: str = "asia-northeast1"
    vertex_encoder_endpoint_id: str = ""
    vertex_predict_timeout_seconds: float = 30.0

    # --- Phase 6 /search rerank (optional bolt-on) ---------------------------
    # When False, /search returns candidates in lexical_rank order with score=None.
    # When True, the API calls the configured Vertex AI reranker endpoint.
    enable_rerank: bool = False
    vertex_reranker_endpoint_id: str = ""
    search_cache_ttl_seconds: int = 120
    search_cache_maxsize: int = 2048

    # --- Phase 6 T6 — RAG via Gemini ----------------------------------------
    # ``enable_rag=False`` keeps the /rag endpoint unwired (returns 503).
    # When True and the Generator adapter successfully constructs, /rag
    # internally invokes hybrid search then asks Gemini to summarize the
    # top-N candidates. Does not alter the /search path.
    enable_rag: bool = False
    gemini_model_name: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.2

    # --- Phase 6 T1 — BQML popularity scorer --------------------------------
    # ``bqml_popularity_enabled=False`` (default) keeps /search payloads
    # unchanged. When True, each SearchResultItem carries an auxiliary
    # popularity_score predicted by the BQML BOOSTED_TREE_REGRESSOR model
    # trained via ``scripts/bqml/train_popularity.sql``. Not added to
    # FEATURE_COLS_RANKER (parity-avoided).
    bqml_popularity_enabled: bool = False
    bqml_popularity_model_fqn: str = ""
