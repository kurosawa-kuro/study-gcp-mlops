"""Concrete candidate retrieval + log-write adapters.

Three adapters live here:

* :class:`BigQueryCandidateRetriever` — hybrid retrieval:
    lexical (Meilisearch) + semantic (BigQuery VECTOR_SEARCH) + RRF fusion,
    then feature enrichment via BigQuery joins.
* :class:`PubSubRankingLogPublisher` / :class:`PubSubFeedbackRecorder` — write
  events to the Pub/Sub topics declared by the runtime module.
* :class:`NoopRankingLogPublisher` / :class:`NoopFeedbackRecorder` — null
  implementations used when the matching topic is unconfigured (local dev).

The Pub/Sub publishers serialize to JSON the same way
:class:`app.services.adapters.publisher.PubSubPublisher` does, so the BQ Subscription
consumes identical payload shapes. Publisher client construction is lazy so
unit tests can instantiate the noop variants without GCP creds.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from google.api_core import exceptions as google_exceptions
from google.cloud import bigquery

from app.services.adapters.semantic_search import BigQuerySemanticSearch
from app.services.protocols.candidate_retriever import Candidate
from app.services.protocols.lexical_search import LexicalSearchPort
from app.services.protocols.semantic_search import SemanticSearchPort
from app.services.ranking import RRF_K, rrf_fuse

# Phase 6 Run 1 で、ranking-log topic の pubsub.publisher 権限欠落 (Terraform state
# と GCP 側の非対称 drift) で /search が 500 を返す事故が発生。Cloud Logging 側
# ではデフォルトの PermissionDenied がそのまま出るだけで「どの topic / どの SA /
# 第二・第三候補は何か」が読み取れず現場復旧に一定の時間がかかったので、
# publish 時点で root-cause 候補を並べて記録するようにした。
_publisher_logger = logging.getLogger("app.pubsub_publisher")


def _runtime_sa_hint() -> str:
    """Best-effort identity label for the current worker (no auth round trip)."""
    return (
        os.getenv("K_SERVICE_ACCOUNT", "")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        or os.getenv("CLOUD_RUN_SERVICE_ACCOUNT", "")
        or "<unknown-sa>"
    )


def _log_publish_failure(
    *,
    where: str,
    topic_path: str,
    exc: BaseException,
) -> None:
    """Structured diagnostics for Pub/Sub publish failures.

    ranking-log / search-feedback / retrain-trigger 共通で使う。root cause
    候補を 1〜3 列挙して、現場 operator が Cloud Logging の 1 行で切り分け
    できるようにする。
    """
    hints: list[str]
    if isinstance(exc, google_exceptions.PermissionDenied):
        hints = [
            "H1: runtime SA (sa-api) に roles/pubsub.publisher が欠落 — "
            "`gcloud pubsub topics get-iam-policy <topic>` で確認、"
            "`terraform apply` で tfstate と GCP を再同期 (Phase 6 Run 1 の drift)",
            "H2: Pub/Sub API (pubsub.googleapis.com) が project で disable — "
            "`gcloud services list --enabled | grep pubsub`",
            "H3: topic が別 project に作られた / 名前ミスマッチ — "
            "topic_path をダンプして project 部分を確認",
        ]
    elif isinstance(exc, google_exceptions.NotFound):
        hints = [
            "H1: topic が存在しない (destroy-all の後など) — "
            "`gcloud pubsub topics list --project=<id>`",
            "H2: topic 名の typo (env `RANKING_LOG_TOPIC` / `FEEDBACK_TOPIC` / `RETRAIN_TOPIC`)",
            "H3: project id ミスマッチ (publisher_client は settings.project_id から topic_path 組み立て)",
        ]
    elif isinstance(exc, (google_exceptions.DeadlineExceeded, TimeoutError)):
        hints = [
            "H1: Pub/Sub API 側でスロットリング / 一時的な遅延",
            "H2: publisher client の batching 中にローカル timeout (.result(timeout=5) 固定)",
            "H3: Cloud Run 側で egress が詰まっている (VPC connector や outbound 制限)",
        ]
    else:
        hints = [
            "H1: 未分類の gRPC / network 例外 — exc.__class__ と grpc status を確認",
            "H2: payload JSON 化で非 ASCII / datetime 等の serialize 失敗 (直前の TypeError を探す)",
            "H3: pubsub_v1.PublisherClient の credentials 初期化失敗 (ADC 未設定)",
        ]
    _publisher_logger.error(
        "pubsub.publish FAILED where=%s topic_path=%s sa_hint=%s exc_type=%s exc=%s hints=%s",
        where,
        topic_path,
        _runtime_sa_hint(),
        type(exc).__name__,
        exc,
        " | ".join(hints),
    )


class BigQueryCandidateRetriever:
    """Hybrid candidate generation via lexical + semantic retrieval.

    Args:
        project_id: GCP project.
        lexical: lexical search adapter (Meilisearch).
        embeddings_table: fully-qualified ``project.dataset.table`` for
            ``feature_mart.property_embeddings`` (768d vectors). Used to
            construct the default Phase 5 semantic backend when ``semantic``
            is not explicitly passed.
        features_table: ``property_features_daily`` fully-qualified name
            (for ctr / fav_rate / inquiry_rate enrichment).
        properties_table: ``feature_mart.properties_cleaned`` for rent /
            walk_min / age_years / area_m2 / pet_ok / layout filter columns.
        client: optional pre-built BQ client (tests).
        semantic: Phase 6 T3 — alternative ``SemanticSearchPort``
            implementation (e.g. ``VertexVectorSearchSemantic``). Defaults to
            ``BigQuerySemanticSearch`` over ``embeddings_table`` so existing
            Phase 5 constructor call-sites keep working unchanged.
    """

    def __init__(
        self,
        *,
        project_id: str,
        lexical: LexicalSearchPort,
        embeddings_table: str,
        features_table: str,
        properties_table: str,
        client: bigquery.Client | None = None,
        semantic: SemanticSearchPort | None = None,
    ) -> None:
        self._lexical = lexical
        self._embeddings_table = embeddings_table
        self._features_table = features_table
        self._properties_table = properties_table
        self._client = client or bigquery.Client(project=project_id)
        self._semantic: SemanticSearchPort = semantic or BigQuerySemanticSearch(
            embeddings_table=embeddings_table,
            properties_table=properties_table,
            client=self._client,
        )

    def retrieve(
        self,
        *,
        query_text: str,
        query_vector: list[float],
        filters: dict[str, Any],
        top_k: int,
    ) -> list[Candidate]:
        lexical_results = self._lexical.search(query=query_text, filters=filters, top_k=200)
        semantic_results = self._semantic.search(
            query_vector=query_vector, filters=filters, top_k=200
        )

        semantic_rank_pairs = [(pid, rank) for pid, rank, _ in semantic_results]
        fused_ids = rrf_fuse(
            lexical_results=lexical_results,
            semantic_results=semantic_rank_pairs,
            top_n=max(top_k, 100),
            k=RRF_K,
        )
        if not fused_ids:
            return []

        lexical_rank_map = {pid: rank for pid, rank in lexical_results}
        semantic_rank_map = {pid: rank for pid, rank, _ in semantic_results}
        me5_score_map = {pid: score for pid, _, score in semantic_results}
        rrf_rank_map = {pid: rank for rank, pid in enumerate(fused_ids, start=1)}

        return self._enrich_from_bq(
            property_ids=fused_ids,
            lexical_rank_map=lexical_rank_map,
            semantic_rank_map=semantic_rank_map,
            me5_score_map=me5_score_map,
            rrf_rank_map=rrf_rank_map,
        )

    def _enrich_from_bq(
        self,
        *,
        property_ids: list[str],
        lexical_rank_map: dict[str, int],
        semantic_rank_map: dict[str, int],
        me5_score_map: dict[str, float],
        rrf_rank_map: dict[str, int],
    ) -> list[Candidate]:
        query = f"""
            WITH selected AS (
              SELECT property_id, offset + 1 AS rrf_rank
              FROM UNNEST(@property_ids) AS property_id WITH OFFSET
            )
            SELECT
              s.property_id,
              s.rrf_rank,
              p.rent AS p_rent,
              p.walk_min AS p_walk_min,
              p.age_years AS p_age_years,
              p.area_m2 AS p_area_m2,
              f.ctr AS f_ctr,
              f.fav_rate AS f_fav_rate,
              f.inquiry_rate AS f_inquiry_rate
            FROM selected s
            LEFT JOIN `{self._properties_table}` p USING (property_id)
            LEFT JOIN (
              SELECT *
              FROM `{self._features_table}`
              WHERE event_date = (SELECT MAX(event_date) FROM `{self._features_table}`)
            ) f USING (property_id)
            ORDER BY s.rrf_rank ASC
        """
        params = [bigquery.ArrayQueryParameter("property_ids", "STRING", property_ids)]
        rows = self._client.query(
            query,
            job_config=bigquery.QueryJobConfig(query_parameters=params),
        ).result()

        candidates: list[Candidate] = []
        for row in rows:
            property_id = str(row["property_id"])
            lexical_rank = lexical_rank_map.get(property_id, 10_000)
            semantic_rank = semantic_rank_map.get(property_id, 10_000)
            me5_score = me5_score_map.get(property_id, 0.0)
            candidates.append(
                Candidate(
                    property_id=property_id,
                    lexical_rank=lexical_rank,
                    semantic_rank=semantic_rank,
                    me5_score=me5_score,
                    property_features={
                        "rent": row["p_rent"],
                        "walk_min": row["p_walk_min"],
                        "age_years": row["p_age_years"],
                        "area_m2": row["p_area_m2"],
                        "ctr": row["f_ctr"],
                        "fav_rate": row["f_fav_rate"],
                        "inquiry_rate": row["f_inquiry_rate"],
                        "rrf_rank": rrf_rank_map.get(property_id),
                    },
                )
            )
        candidates.sort(key=lambda c: rrf_rank_map.get(c.property_id, 10_000))
        return candidates


class PubSubRankingLogPublisher:
    """Writes ranking-log rows to the ``ranking-log`` Pub/Sub topic."""

    def __init__(self, *, project_id: str, topic: str) -> None:
        from google.cloud import pubsub_v1  # type: ignore[attr-defined]

        self._client = pubsub_v1.PublisherClient()
        self._topic_path = self._client.topic_path(project_id, topic)
        _publisher_logger.info(
            "pubsub.publisher init class=%s topic_path=%s sa_hint=%s",
            type(self).__name__,
            self._topic_path,
            _runtime_sa_hint(),
        )

    def publish_candidates(
        self,
        *,
        request_id: str,
        candidates: list[Candidate],
        final_ranks: list[int],
        scores: list[float | None],
        model_path: str | None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        for cand, final_rank, score in zip(candidates, final_ranks, scores, strict=True):
            payload = {
                "request_id": request_id,
                "ts": ts,
                "property_id": cand.property_id,
                "schema_version": 2,
                "lexical_rank": cand.lexical_rank,
                "semantic_rank": cand.semantic_rank,
                "rrf_rank": cand.property_features.get("rrf_rank"),
                "final_rank": final_rank,
                "score": score,
                "me5_score": cand.me5_score,
                "features": {
                    "rent": _as_float(cand.property_features.get("rent")),
                    "walk_min": _as_float(cand.property_features.get("walk_min")),
                    "age_years": _as_float(cand.property_features.get("age_years")),
                    "area_m2": _as_float(cand.property_features.get("area_m2")),
                    "ctr": _as_float(cand.property_features.get("ctr")),
                    "fav_rate": _as_float(cand.property_features.get("fav_rate")),
                    "inquiry_rate": _as_float(cand.property_features.get("inquiry_rate")),
                    "me5_score": cand.me5_score,
                    "lexical_rank": float(cand.lexical_rank),
                    "semantic_rank": float(cand.semantic_rank),
                },
                "model_path": model_path,
            }
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            try:
                self._client.publish(self._topic_path, data).result(timeout=5)
            except Exception as exc:
                _log_publish_failure(
                    where="PubSubRankingLogPublisher.publish_candidates",
                    topic_path=self._topic_path,
                    exc=exc,
                )
                raise


class PubSubFeedbackRecorder:
    """Writes feedback events to the ``search-feedback`` Pub/Sub topic."""

    def __init__(self, *, project_id: str, topic: str) -> None:
        from google.cloud import pubsub_v1  # type: ignore[attr-defined]

        self._client = pubsub_v1.PublisherClient()
        self._topic_path = self._client.topic_path(project_id, topic)
        _publisher_logger.info(
            "pubsub.publisher init class=%s topic_path=%s sa_hint=%s",
            type(self).__name__,
            self._topic_path,
            _runtime_sa_hint(),
        )

    def record(self, *, request_id: str, property_id: str, action: str) -> None:
        payload = {
            "request_id": request_id,
            "property_id": property_id,
            "action": action,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self._client.publish(self._topic_path, data).result(timeout=5)
        except Exception as exc:
            _log_publish_failure(
                where="PubSubFeedbackRecorder.record",
                topic_path=self._topic_path,
                exc=exc,
            )
            raise


class NoopRankingLogPublisher:
    def publish_candidates(
        self,
        *,
        request_id: str,
        candidates: list[Candidate],
        final_ranks: list[int],
        scores: list[float | None],
        model_path: str | None,
    ) -> None:
        return None


class NoopFeedbackRecorder:
    def record(self, *, request_id: str, property_id: str, action: str) -> None:
        return None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)  # type: ignore[arg-type]
