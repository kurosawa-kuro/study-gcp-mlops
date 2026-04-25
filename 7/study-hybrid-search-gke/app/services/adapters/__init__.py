"""Production adapters — concrete implementations backed by external systems.

Phase B-3 separated test-doubles / null-implementations into
``app/services/fakes/``. This module re-exports both production adapters
and (for backward compat) the ``fakes/`` symbols that previously lived
here. Phase D will remove the fakes re-exports once callers (composition
root, tests) have moved to ``from app.services.fakes import ...``.
"""

from app.services.fakes import (
    InMemoryTTLCacheStore,
    NoopCacheStore,
    NoopFeedbackRecorder,
    NoopLexicalSearch,
    NoopRankingLogPublisher,
)

from .bigquery_candidate_retriever import BigQueryCandidateRetriever
from .cache_store import MemorystoreRedisCacheStore
from .pubsub_feedback_recorder import PubSubFeedbackRecorder
from .pubsub_ranking_log_publisher import PubSubRankingLogPublisher
from .kserve_encoder import KServeEncoder
from .kserve_reranker import KServeReranker
from .lexical_search import MeilisearchLexical
from .publisher import PubSubPublisher
from .retrain import BigQueryRetrainQueries, create_retrain_queries

__all__ = [
    # Production adapters
    "BigQueryCandidateRetriever",
    "BigQueryRetrainQueries",
    "KServeEncoder",
    "KServeReranker",
    "MeilisearchLexical",
    "MemorystoreRedisCacheStore",
    "PubSubFeedbackRecorder",
    "PubSubPublisher",
    "PubSubRankingLogPublisher",
    "create_retrain_queries",
    # Re-exported from app.services.fakes for backward compat (Phase B-3 transitional)
    "InMemoryTTLCacheStore",
    "NoopCacheStore",
    "NoopFeedbackRecorder",
    "NoopLexicalSearch",
    "NoopRankingLogPublisher",
]
