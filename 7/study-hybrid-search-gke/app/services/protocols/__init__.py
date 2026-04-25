"""API-side Ports — Protocols consumed by services / handlers.

Phase B-1 split each Protocol into its own file (1 Port = 1 file). The
``Candidate`` dataclass moved to ``app/domain/candidate.py`` and is
re-exported here for backward compatibility with existing adapter
imports (Phase B-2 sweeps callers to import from ``app.domain``).
"""

from app.domain.candidate import Candidate

from ._types import LexicalResult, SemanticResult
from .cache_store import CacheStore
from .candidate_retriever import CandidateRetriever
from .encoder_client import EncoderClient
from .feedback_recorder import FeedbackRecorder
from .lexical_search import LexicalSearchPort
from .popularity_scorer import PopularityScorer
from .publisher import NoopPublisher, PredictionPublisher
from .ranking_log_publisher import RankingLogPublisher
from .reranker_client import RerankerClient, RerankerExplainer
from .retrain_queries import RetrainQueries
from .semantic_search import SemanticSearchPort

__all__ = [
    "CacheStore",
    "Candidate",
    "CandidateRetriever",
    "EncoderClient",
    "FeedbackRecorder",
    "LexicalResult",
    "LexicalSearchPort",
    "NoopPublisher",
    "PopularityScorer",
    "PredictionPublisher",
    "RankingLogPublisher",
    "RerankerClient",
    "RerankerExplainer",
    "RetrainQueries",
    "SemanticResult",
    "SemanticSearchPort",
]
