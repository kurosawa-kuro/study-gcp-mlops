"""Composition root for the hybrid-search FastAPI app.

This module owns DI wiring. ``ContainerBuilder`` translates :class:`ApiSettings`
into a fully-constructed :class:`Container` of adapters and services. The
``Container`` is immutable; handlers (Phase A-2) consume it via FastAPI
``Depends``.

Phase A-1 status: factories were lifted out of ``app/main.py`` (was 699 lines;
factories occupied L67-328). ``app/main.py`` calls :meth:`ContainerBuilder.build`
during ``lifespan`` and stores the result on ``app.state.container``.

Adding a new component means: define a new ``_build_*`` helper here, add a
field to ``Container``, wire it in ``ContainerBuilder.build``. ``app/main.py``
should not grow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.adapters import (
    BigQueryCandidateRetriever,
    BigQueryRetrainQueries,
    KServeEncoder,
    KServeReranker,
    MeilisearchLexical,
    PubSubFeedbackRecorder,
    PubSubPublisher,
    PubSubRankingLogPublisher,
)
from app.services.fakes import (
    InMemoryTTLCacheStore,
    NoopCacheStore,
    NoopFeedbackRecorder,
    NoopLexicalSearch,
    NoopRankingLogPublisher,
)
from app.services.config import ApiSettings
from app.services.protocols import (
    CacheStore,
    CandidateRetriever,
    EncoderClient,
    FeedbackRecorder,
    LexicalSearchPort,
    PredictionPublisher,
    RankingLogPublisher,
    RerankerClient,
)
from app.services.feedback_service import FeedbackService
from app.services.protocols.generator import Generator
from app.services.protocols.popularity_scorer import PopularityScorer
from app.services.protocols.retrain_queries import RetrainQueries
from app.services.protocols.semantic_search import SemanticSearchPort
from app.services.rag_service import RagService
from app.services.rag_summarizer import RagSummarizer
from app.services.search_service import SearchService
from ml.common.logging import get_logger


@dataclass(frozen=True)
class Container:
    """Immutable bag of fully-constructed adapters and services.

    All fields are populated once at app startup by
    :meth:`ContainerBuilder.build`. Handlers receive the container via
    FastAPI ``Depends`` (Phase A-2). Optional fields are ``None`` when the
    corresponding feature flag is disabled or required configuration is
    missing — handlers must check for ``None`` before use.

    Notes:
    - ``candidate_retriever_alt`` is the Phase 6 T7 副経路 (Discovery Engine
      via Agent Builder), only built when ``LEXICAL_BACKEND=agent_builder``
      and the engine is configured. Default lexical (Meilisearch) stays as
      ``candidate_retriever`` (親リポ non-negotiable).
    - ``model_path`` mirrors ``reranker_client.model_path`` for endpoints
      that need to surface the active reranker model identifier without
      pulling the client.
    """

    settings: ApiSettings
    training_runs_table: str

    retrain_trigger_publisher: PredictionPublisher | None
    retrain_queries: RetrainQueries

    candidate_retriever: CandidateRetriever | None
    candidate_retriever_alt: CandidateRetriever | None

    encoder_client: EncoderClient | None
    encoder_model_path: str | None

    reranker_client: RerankerClient | None
    model_path: str | None

    rag_summarizer: RagSummarizer | None
    popularity_scorer: PopularityScorer | None
    lexical_alt: LexicalSearchPort | None

    ranking_log_publisher: RankingLogPublisher
    feedback_recorder: FeedbackRecorder
    search_cache: CacheStore

    # Services (Phase D-1) — constructed once at startup, depend only on
    # the adapter Ports above. Handlers receive these via FastAPI Depends.
    search_service: SearchService
    feedback_service: FeedbackService
    rag_service: RagService | None  # None when ENABLE_RAG=False


class ContainerBuilder:
    """Builds a :class:`Container` from :class:`ApiSettings`.

    Splitting build into per-component ``_build_*`` helpers keeps each
    selection rule narrow (one feature flag → one adapter). The helpers are
    method-level rather than module-level functions so they share the
    ``self._settings`` reference without threading it through every call.
    """

    def __init__(self, settings: ApiSettings) -> None:
        self._settings = settings
        self._logger = get_logger("app")
        self._bq_client: Any = None  # cached, see _bigquery()

    def _bigquery(self) -> Any:
        """Phase A-4 — single ``bigquery.Client`` shared across adapters.

        Multiple adapters (CandidateRetriever / SemanticSearch /
        PopularityScorer / RetrainQueries) previously each instantiated
        their own client. Centralising means one credentials round-trip,
        one connection pool, and one place to fail at startup if BigQuery
        is unreachable.

        Lazy + cached: the first caller pays the construction cost; later
        callers get the same instance. Returns ``None``-typed for unit
        tests that pass through fakes.
        """
        if self._bq_client is None:
            from google.cloud import bigquery

            self._bq_client = bigquery.Client(project=self._settings.project_id)
        return self._bq_client

    def build(self) -> Container:
        settings = self._settings
        training_runs_table = (
            f"{settings.project_id}.{settings.bq_dataset_mlops}."
            f"{settings.bq_table_training_runs}"
        )

        retrain_trigger_publisher = self._build_retrain_publisher()
        retrain_queries: RetrainQueries = BigQueryRetrainQueries(
            client=self._bigquery(),
            training_runs_table=training_runs_table,
        )

        if settings.enable_search:
            encoder_client, encoder_model_path = self._build_encoder_client()
            candidate_retriever: CandidateRetriever | None = self._build_candidate_retriever()
            # Phase 6 T7 副経路: 親 Meilisearch 経路を残したまま、
            # ?lexical=agent_builder で Discovery Engine を引く sibling
            # retriever を別 instance として保持する。
            alt_lexical = self._build_agent_builder_lexical()
            candidate_retriever_alt: CandidateRetriever | None
            if alt_lexical is not None:
                candidate_retriever_alt = self._build_candidate_retriever(
                    override_lexical=alt_lexical
                )
            else:
                candidate_retriever_alt = None
        else:
            encoder_client = None
            encoder_model_path = None
            candidate_retriever = None
            candidate_retriever_alt = None

        reranker_client, model_path = self._build_reranker_client()
        rag_summarizer = self._build_rag_summarizer()
        popularity_scorer = self._build_popularity_scorer()
        lexical_alt = self._build_agent_builder_lexical()

        ranking_log_publisher = self._build_ranking_log_publisher()
        feedback_recorder = self._build_feedback_recorder()
        search_cache = self._build_search_cache()

        # Phase D-1 — service composition. Services are stateless wrappers
        # around the Ports above; constructed once at startup so handlers
        # don't pay per-request allocation cost.
        search_service = SearchService(
            retriever_default=candidate_retriever,
            retriever_alt=candidate_retriever_alt,
            encoder=encoder_client,
            publisher=ranking_log_publisher,
            reranker=reranker_client,
            popularity_scorer=popularity_scorer,
            cache=search_cache,
            cache_ttl_seconds=settings.search_cache_ttl_seconds,
        )
        feedback_service = FeedbackService(recorder=feedback_recorder)
        rag_service: RagService | None
        if rag_summarizer is not None:
            rag_service = RagService(
                search_service=search_service,
                summarizer=rag_summarizer,
            )
        else:
            rag_service = None

        self._logger.info(
            "Startup complete; search_enabled=%s rerank_enabled=%s rag_enabled=%s "
            "model_path=%s",
            settings.enable_search,
            reranker_client is not None,
            rag_service is not None,
            model_path,
        )

        return Container(
            settings=settings,
            training_runs_table=training_runs_table,
            retrain_trigger_publisher=retrain_trigger_publisher,
            retrain_queries=retrain_queries,
            candidate_retriever=candidate_retriever,
            candidate_retriever_alt=candidate_retriever_alt,
            encoder_client=encoder_client,
            encoder_model_path=encoder_model_path,
            reranker_client=reranker_client,
            model_path=model_path,
            rag_summarizer=rag_summarizer,
            popularity_scorer=popularity_scorer,
            lexical_alt=lexical_alt,
            ranking_log_publisher=ranking_log_publisher,
            feedback_recorder=feedback_recorder,
            search_cache=search_cache,
            search_service=search_service,
            feedback_service=feedback_service,
            rag_service=rag_service,
        )

    # ------------------------------------------------------------------ factories

    def _build_retrain_publisher(self) -> PredictionPublisher | None:
        settings = self._settings
        if not settings.retrain_topic:
            return None
        return PubSubPublisher(project_id=settings.project_id, topic=settings.retrain_topic)

    def _build_ranking_log_publisher(self) -> RankingLogPublisher:
        settings = self._settings
        if not settings.ranking_log_topic:
            return NoopRankingLogPublisher()
        return PubSubRankingLogPublisher(
            project_id=settings.project_id, topic=settings.ranking_log_topic
        )

    def _build_feedback_recorder(self) -> FeedbackRecorder:
        settings = self._settings
        if not settings.feedback_topic:
            return NoopFeedbackRecorder()
        return PubSubFeedbackRecorder(
            project_id=settings.project_id, topic=settings.feedback_topic
        )

    def _build_candidate_retriever(
        self,
        *,
        override_lexical: LexicalSearchPort | None = None,
    ) -> BigQueryCandidateRetriever:
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
        lexical: LexicalSearchPort
        if override_lexical is not None:
            # Phase 6 T7 — sibling retriever with alt lexical backend; never
            # replaces the primary Meilisearch path.
            lexical = override_lexical
        elif settings.meili_base_url:
            # meili_master_key (Secret Manager) を優先、未設定時は meili_api_key へフォールバック。
            _meili_key = settings.meili_master_key.get_secret_value() or settings.meili_api_key
            lexical = MeilisearchLexical(
                base_url=settings.meili_base_url,
                index_name=settings.meili_index_name,
                api_key=_meili_key,
                require_identity_token=settings.meili_require_identity_token,
            )
        else:
            lexical = NoopLexicalSearch()

        # Phase 6 T3 — pick semantic backend; default keeps Phase 5 BQ path.
        semantic = self._build_semantic_search(properties_table=properties_table)
        return BigQueryCandidateRetriever(
            project_id=settings.project_id,
            lexical=lexical,
            embeddings_table=embeddings_table,
            features_table=features_table,
            properties_table=properties_table,
            semantic=semantic,
            client=self._bigquery(),
        )

    def _build_semantic_search(
        self,
        *,
        properties_table: str,
    ) -> SemanticSearchPort | None:
        """Select the SemanticSearchPort implementation.

        Returns ``None`` to let :class:`BigQueryCandidateRetriever` construct
        the Phase 5 default (``BigQuerySemanticSearch``) lazily from its
        injected BigQuery client. Returns a concrete adapter when
        ``settings.semantic_backend == "vertex"`` and the Matching Engine
        endpoint / deployed_index IDs are configured.

        Phase A-4: Vertex backend is eagerly prepared at startup via
        ``adapter.prepare()``; failures downgrade to ``None`` (BQ fallback).
        """
        settings = self._settings
        if settings.semantic_backend != "vertex":
            # "bq" (default) — let BigQueryCandidateRetriever construct the
            # default BigQuerySemanticSearch internally so we don't manage a
            # second BQ client lifecycle here.
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
        from app.services.adapters.semantic_search import VertexVectorSearchSemantic

        try:
            adapter = VertexVectorSearchSemantic(
                project_id=settings.project_id,
                location=settings.vertex_location,
                index_endpoint_id=settings.vertex_vector_search_index_endpoint_id,
                deployed_index_id=settings.vertex_vector_search_deployed_index_id,
                properties_table=properties_table,
                client=self._bigquery(),
            )
            adapter.prepare()
        except Exception:
            self._logger.exception(
                "Failed to prepare VertexVectorSearchSemantic — falling back to "
                "BigQuery VECTOR_SEARCH"
            )
            return None
        return adapter

    def _build_search_cache(self) -> CacheStore:
        settings = self._settings
        if settings.search_cache_ttl_seconds <= 0:
            return NoopCacheStore()
        return InMemoryTTLCacheStore(
            maxsize=settings.search_cache_maxsize,
            default_ttl_seconds=settings.search_cache_ttl_seconds,
        )

    def _build_encoder_client(self) -> tuple[EncoderClient | None, str | None]:
        settings = self._settings
        # Phase 5 Run 2 で endpoint_id 未設定により API が silently 起動不能だった
        # 再発防止: 設定の絶対値と判定結果を毎回明示する。
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

    def _build_reranker_client(self) -> tuple[RerankerClient | None, str | None]:
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

    def _build_rag_summarizer(self) -> RagSummarizer | None:
        """Phase 6 T6 — RAG summarizer; ``None`` when disabled.

        Phase A-4: ``GeminiGenerator.prepare()`` runs at startup so the
        ``vertexai`` SDK init failure surface here (and thereby in startup
        logs / readyz semantics) instead of on the first /rag request.
        """
        settings = self._settings
        if not settings.enable_rag:
            return None
        try:
            from app.services.adapters.gemini_generator import GeminiGenerator

            adapter = GeminiGenerator(
                project_id=settings.project_id,
                location=settings.vertex_location,
                model_name=settings.gemini_model_name,
                temperature=settings.gemini_temperature,
            )
            adapter.prepare()
            generator: Generator = adapter
        except Exception:
            self._logger.exception("Failed to initialize Gemini generator for /rag")
            return None
        return RagSummarizer(generator=generator)

    def _build_popularity_scorer(self) -> PopularityScorer | None:
        """Phase 6 T1 — optional BQML popularity scorer; ``None`` when disabled."""
        settings = self._settings
        if not settings.bqml_popularity_enabled:
            return None
        model_fqn = settings.bqml_popularity_model_fqn or (
            f"{settings.project_id}.{settings.bq_dataset_mlops}.property_popularity"
        )
        properties_table = (
            f"{settings.project_id}.{settings.bq_dataset_feature_mart}."
            f"{settings.bq_table_properties_cleaned}"
        )
        features_table = (
            f"{settings.project_id}.{settings.bq_dataset_feature_mart}."
            f"{settings.bq_table_property_features_daily}"
        )
        try:
            from app.services.adapters.bqml_popularity_scorer import BQMLPopularityScorer

            return BQMLPopularityScorer(
                project_id=settings.project_id,
                model_fqn=model_fqn,
                properties_table=properties_table,
                features_table=features_table,
                client=self._bigquery(),
            )
        except Exception:
            self._logger.exception("Failed to initialize BQML popularity scorer")
            return None

    def _build_agent_builder_lexical(self) -> LexicalSearchPort | None:
        """Phase 6 T7 — optional Discovery Engine lexical adapter.

        Returned adapter is wired into both:
        - ``Container.lexical_alt`` for direct service-level access
        - ``Container.candidate_retriever_alt`` (a sibling retriever) reached
          via ``/search?lexical=agent_builder``.
        Default lexical (Meilisearch) is unaffected.
        """
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
