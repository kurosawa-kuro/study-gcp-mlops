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

from app.container import InfraBuilder, MlBuilder, SearchBuilder
from app.services.feedback_service import FeedbackService
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
from app.services.protocols.popularity_scorer import PopularityScorer
from app.services.protocols.retrain_queries import RetrainQueries
from app.services.protocols.semantic_search import SemanticSearchPort
from app.services.rag_service import RagService
from app.services.rag_summarizer import RagSummarizer
from app.services.search_service import SearchService
from app.settings import ApiSettings
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
        infra = InfraBuilder(self).build()
        search = SearchBuilder(self).build()
        ml = MlBuilder(self).build()

        # Phase D-1 — service composition. Services are stateless wrappers
        # around the Ports above; constructed once at startup so handlers
        # don't pay per-request allocation cost.
        search_service = SearchService(
            retriever_default=search.candidate_retriever,
            retriever_alt=search.candidate_retriever_alt,
            encoder=search.encoder_client,
            publisher=infra.ranking_log_publisher,
            reranker=search.reranker_client,
            popularity_scorer=ml.popularity_scorer,
            cache=search.search_cache,
            cache_ttl_seconds=settings.search_cache_ttl_seconds,
        )
        feedback_service = FeedbackService(recorder=infra.feedback_recorder)
        rag_service: RagService | None
        if ml.rag_summarizer is not None:
            rag_service = RagService(
                search_service=search_service,
                summarizer=ml.rag_summarizer,
            )
        else:
            rag_service = None

        self._logger.info(
            "Startup complete; search_enabled=%s rerank_enabled=%s rag_enabled=%s model_path=%s",
            settings.enable_search,
            search.reranker_client is not None,
            rag_service is not None,
            search.model_path,
        )

        return Container(
            settings=settings,
            training_runs_table=infra.training_runs_table,
            retrain_trigger_publisher=infra.retrain_trigger_publisher,
            retrain_queries=infra.retrain_queries,
            candidate_retriever=search.candidate_retriever,
            candidate_retriever_alt=search.candidate_retriever_alt,
            encoder_client=search.encoder_client,
            encoder_model_path=search.encoder_model_path,
            reranker_client=search.reranker_client,
            model_path=search.model_path,
            rag_summarizer=ml.rag_summarizer,
            popularity_scorer=ml.popularity_scorer,
            lexical_alt=search.lexical_alt,
            ranking_log_publisher=infra.ranking_log_publisher,
            feedback_recorder=infra.feedback_recorder,
            search_cache=search.search_cache,
            search_service=search_service,
            feedback_service=feedback_service,
            rag_service=rag_service,
        )

    # ------------------------------------------------------------------ factories

    def _build_retrain_publisher(self) -> PredictionPublisher | None:
        return InfraBuilder(self).build_retrain_publisher()

    def _build_ranking_log_publisher(self) -> RankingLogPublisher:
        return InfraBuilder(self).build_ranking_log_publisher()

    def _build_feedback_recorder(self) -> FeedbackRecorder:
        return InfraBuilder(self).build_feedback_recorder()

    def _build_candidate_retriever(
        self,
        *,
        override_lexical: LexicalSearchPort | None = None,
    ) -> CandidateRetriever:
        return SearchBuilder(self).build_candidate_retriever(override_lexical=override_lexical)

    def _build_semantic_search(
        self,
        *,
        properties_table: str,
    ) -> SemanticSearchPort | None:
        return SearchBuilder(self).build_semantic_search(properties_table=properties_table)

    def _build_search_cache(self) -> CacheStore:
        return SearchBuilder(self).build_search_cache()

    def _build_encoder_client(self) -> tuple[EncoderClient | None, str | None]:
        return SearchBuilder(self).build_encoder_client()

    def _build_reranker_client(self) -> tuple[RerankerClient | None, str | None]:
        return SearchBuilder(self).build_reranker_client()

    def _build_rag_summarizer(self) -> RagSummarizer | None:
        return MlBuilder(self).build_rag_summarizer()

    def _build_popularity_scorer(self) -> PopularityScorer | None:
        return MlBuilder(self).build_popularity_scorer()

    def _build_agent_builder_lexical(self) -> LexicalSearchPort | None:
        return SearchBuilder(self).build_agent_builder_lexical()
