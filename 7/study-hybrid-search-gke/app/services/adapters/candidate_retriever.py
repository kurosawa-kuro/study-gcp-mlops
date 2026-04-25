"""Backward-compat shim — Phase B-2 split this module.

Adapter classes now live in dedicated files:

* :class:`BigQueryCandidateRetriever` →
  :mod:`app.services.adapters.bigquery_candidate_retriever`
* :class:`PubSubRankingLogPublisher` →
  :mod:`app.services.adapters.pubsub_ranking_log_publisher`
* :class:`PubSubFeedbackRecorder` →
  :mod:`app.services.adapters.pubsub_feedback_recorder`

Shared helpers (``runtime_sa_hint`` / ``log_publish_failure`` / ``as_float``)
moved to :mod:`app.services.adapters._pubsub_diagnostics`.
"""

from app.services.adapters.bigquery_candidate_retriever import BigQueryCandidateRetriever
from app.services.adapters.pubsub_feedback_recorder import PubSubFeedbackRecorder
from app.services.adapters.pubsub_ranking_log_publisher import PubSubRankingLogPublisher

__all__ = [
    "BigQueryCandidateRetriever",
    "PubSubFeedbackRecorder",
    "PubSubRankingLogPublisher",
]
