"""Search-facing dependency assembly.

Scope:
- singleton adapters built once at startup
- helper selection rules for lexical / semantic / cache wiring
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.adapters import (
    BigQueryCandidateRetriever,
    KServeEncoder,
    KServeReranker,
    MeilisearchLexical,
)
from app.services.fakes import InMemoryTTLCacheStore, NoopCacheStore, NoopLexicalSearch
from app.services.protocols import CacheStore, CandidateRetriever, EncoderClient, LexicalSearchPort
from app.services.protocols.reranker_client import RerankerClient
from app.services.protocols.semantic_search import SemanticSearchPort
from app.settings import ApiSettings


class SearchBuilderContext(Protocol):
    _settings: ApiSettings
    _logger: Any

    def _bigquery(self) -> Any: ...


@dataclass(frozen=True)
class SearchComponents:
    candidate_retriever: CandidateRetriever | None
    candidate_retriever_alt: CandidateRetriever | None
    encoder_client: EncoderClient | None
    encoder_model_path: str | None
    reranker_client: RerankerClient | None
    model_path: str | None
    lexical_alt: LexicalSearchPort | None
    search_cache: CacheStore


class SearchBuilder:
    """Build search-path adapters.

    All produced objects are startup singletons reused across requests.
    """

    def __init__(self, context: SearchBuilderContext) -> None:
        self._context = context

    @property
    def _settings(self) -> ApiSettings:
        return self._context._settings

    @property
    def _logger(self) -> Any:
        return self._context._logger

    def build(self) -> SearchComponents:
        settings = self._settings
        if settings.enable_search:
            encoder_client, encoder_model_path = self.build_encoder_client()
            candidate_retriever = self.build_candidate_retriever()
            alt_lexical = self.build_agent_builder_lexical()
            candidate_retriever_alt = (
                self.build_candidate_retriever(override_lexical=alt_lexical)
                if alt_lexical is not None
                else None
            )
        else:
            encoder_client = None
            encoder_model_path = None
            candidate_retriever = None
            candidate_retriever_alt = None
        reranker_client, model_path = self.build_reranker_client()
        lexical_alt = self.build_agent_builder_lexical()
        search_cache = self.build_search_cache()
        return SearchComponents(
            candidate_retriever=candidate_retriever,
            candidate_retriever_alt=candidate_retriever_alt,
            encoder_client=encoder_client,
            encoder_model_path=encoder_model_path,
            reranker_client=reranker_client,
            model_path=model_path,
            lexical_alt=lexical_alt,
            search_cache=search_cache,
        )

    def build_candidate_retriever(
        self,
        *,
        override_lexical: LexicalSearchPort | None = None,
    ) -> CandidateRetriever:
        settings = self._settings
        embeddings_table = (
            f"{settings.project_id}.{settings.bq_dataset_feature_mart}."
            f"{settings.bq_table_property_embeddings}"
        )
        features_table = (
            f"{settings.project_id}.{settings.bq_dataset_feature_mart}."
            f"{settings.bq_table_property_features_daily}"
        )
        properties_table = (
            f"{settings.project_id}.{settings.bq_dataset_feature_mart}."
            f"{settings.bq_table_properties_cleaned}"
        )
        lexical = self._resolve_lexical_search(override_lexical=override_lexical)
        semantic = self.build_semantic_search(properties_table=properties_table)
        return BigQueryCandidateRetriever(
            project_id=settings.project_id,
            lexical=lexical,
            embeddings_table=embeddings_table,
            features_table=features_table,
            properties_table=properties_table,
            semantic=semantic,
            client=self._context._bigquery(),
        )

    def _resolve_lexical_search(
        self,
        *,
        override_lexical: LexicalSearchPort | None,
    ) -> LexicalSearchPort:
        settings = self._settings
        if override_lexical is not None:
            return override_lexical
        if settings.meili_base_url:
            meili_key = settings.meili_master_key.get_secret_value() or settings.meili_api_key
            return MeilisearchLexical(
                base_url=settings.meili_base_url,
                index_name=settings.meili_index_name,
                api_key=meili_key,
                require_identity_token=settings.meili_require_identity_token,
            )
        return NoopLexicalSearch()

    def build_semantic_search(
        self,
        *,
        properties_table: str,
    ) -> SemanticSearchPort | None:
        settings = self._settings
        if settings.semantic_backend != "vertex":
            return None
        if not settings.vertex_vector_search_index_endpoint_id:
            self._logger.warning(
                "SEMANTIC_BACKEND=vertex but VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID is empty; "
                "falling back to BigQuery VECTOR_SEARCH"
            )
            return None
        if not settings.vertex_vector_search_deployed_index_id:
            self._logger.warning(
                "SEMANTIC_BACKEND=vertex but VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID is empty; "
                "falling back to BigQuery VECTOR_SEARCH"
            )
            return None
        from app.services.adapters.vertex_vector_search_semantic import (
            VertexVectorSearchSemantic,
        )

        try:
            adapter = VertexVectorSearchSemantic(
                project_id=settings.project_id,
                location=settings.vertex_location,
                index_endpoint_id=settings.vertex_vector_search_index_endpoint_id,
                deployed_index_id=settings.vertex_vector_search_deployed_index_id,
                properties_table=properties_table,
                client=self._context._bigquery(),
            )
            adapter.prepare()
        except Exception:
            self._logger.exception(
                "Failed to prepare VertexVectorSearchSemantic — falling back to BigQuery VECTOR_SEARCH"
            )
            return None
        return adapter

    def build_search_cache(self) -> CacheStore:
        settings = self._settings
        if settings.search_cache_ttl_seconds <= 0:
            return NoopCacheStore()
        return InMemoryTTLCacheStore(
            maxsize=settings.search_cache_maxsize,
            default_ttl_seconds=settings.search_cache_ttl_seconds,
        )

    def build_encoder_client(self) -> tuple[EncoderClient | None, str | None]:
        settings = self._settings
        self._logger.info(
            "build_encoder_client enable_search=%s kserve_encoder_url=%r timeout=%.1fs",
            settings.enable_search,
            settings.kserve_encoder_url,
            settings.kserve_predict_timeout_seconds,
        )
        if not settings.kserve_encoder_url:
            self._logger.warning(
                "ENABLE_SEARCH=true but KSERVE_ENCODER_URL is empty — encoder client DISABLED. "
                "Check infra/manifests/search-api/deployment.yaml env `KSERVE_ENCODER_URL`. "
                "Expected cluster-local: "
                "http://property-encoder.kserve-inference.svc.cluster.local/predict"
            )
            return None, None
        try:
            client = KServeEncoder(
                endpoint_url=settings.kserve_encoder_url,
                timeout_seconds=settings.kserve_predict_timeout_seconds,
            )
        except Exception:
            self._logger.exception(
                "Failed to initialize KServe encoder client url=%r",
                settings.kserve_encoder_url,
            )
            return None, None
        self._logger.info("encoder client READY endpoint_name=%s", client.endpoint_name)
        return client, client.endpoint_name

    def build_reranker_client(self) -> tuple[RerankerClient | None, str | None]:
        settings = self._settings
        self._logger.info(
            "build_reranker_client enable_rerank=%s kserve_reranker_url=%r timeout=%.1fs",
            settings.enable_rerank,
            settings.kserve_reranker_url,
            settings.kserve_predict_timeout_seconds,
        )
        if not settings.enable_rerank:
            self._logger.info("ENABLE_RERANK=false — reranker client DISABLED (intentional)")
            return None, None
        if not settings.kserve_reranker_url:
            self._logger.warning(
                "ENABLE_RERANK=true but KSERVE_RERANKER_URL is empty — reranker client DISABLED. "
                "Expected cluster-local: "
                "http://property-reranker.kserve-inference.svc.cluster.local"
                "/v1/models/property-reranker:predict"
            )
            return None, None
        try:
            client = KServeReranker(
                endpoint_url=settings.kserve_reranker_url,
                explain_url=settings.kserve_reranker_explain_url or None,
                timeout_seconds=settings.kserve_predict_timeout_seconds,
            )
        except Exception:
            self._logger.exception(
                "Failed to initialize KServe reranker client url=%r",
                settings.kserve_reranker_url,
            )
            return None, None
        self._logger.info("reranker client READY endpoint_name=%s", client.endpoint_name)
        return client, client.endpoint_name

    def build_agent_builder_lexical(self) -> LexicalSearchPort | None:
        settings = self._settings
        if settings.lexical_backend != "agent_builder":
            return None
        if not settings.vertex_agent_builder_engine_id:
            self._logger.warning(
                "LEXICAL_BACKEND=agent_builder but VERTEX_AGENT_BUILDER_ENGINE_ID is empty"
            )
            return None
        try:
            from app.services.adapters.agent_builder_lexical import AgentBuilderLexicalRetriever

            return AgentBuilderLexicalRetriever(
                project_id=settings.project_id,
                location=settings.vertex_agent_builder_location,
                engine_id=settings.vertex_agent_builder_engine_id,
                collection_id=settings.vertex_agent_builder_collection_id,
                serving_config_id=settings.vertex_agent_builder_serving_config_id,
            )
        except Exception:
            self._logger.exception("Failed to initialize Agent Builder lexical adapter")
            return None
