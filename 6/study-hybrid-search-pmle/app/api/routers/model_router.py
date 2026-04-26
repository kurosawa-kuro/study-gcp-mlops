"""``/model/*`` endpoints — hybrid-search のモデル系 API。

- ``GET /model/metrics`` — NDCG@k / HitRate@k / MRR@k の精度評価レポート
  (元 ``/metrics`` で意図されていた API。Prometheus exposition は ``/metrics``
  を専有するので衝突回避のためこのパスへ分離)
- ``GET /model/info`` — encoder / reranker の active 配信先と model_path
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_container
from app.composition_root import Container
from app.schemas.model import (
    AccuracySummary,
    CaseMetric,
    ModelInfoResponse,
    ModelMetricsResponse,
)

router = APIRouter(prefix="/model")


@router.get("/metrics", response_model=ModelMetricsResponse)
def model_metrics(
    container: Annotated[Container, Depends(get_container)],
    k: int = Query(default=10, ge=1, le=100, description="cutoff for NDCG/HitRate/MRR"),
) -> ModelMetricsResponse:
    service = container.model_metrics_service
    if service is None:
        raise HTTPException(status_code=503, detail="model_metrics_service not configured")
    report = service.evaluate(k=k)
    return ModelMetricsResponse(
        cases_file=report.cases_file,
        num_cases=report.num_cases,
        k=report.k,
        summary=AccuracySummary(
            ndcg_at_k=report.summary_ndcg_at_k,
            hit_rate_at_k=report.summary_hit_rate_at_k,
            mrr_at_k=report.summary_mrr_at_k,
        ),
        per_case=[
            CaseMetric(
                name=c.name,
                query=c.query,
                returned=c.returned,
                relevant_total=c.relevant_total,
                matched_in_results=c.matched_in_results,
                ndcg_at_k=c.ndcg_at_k,
                hit_rate_at_k=c.hit_rate_at_k,
                mrr_at_k=c.mrr_at_k,
            )
            for c in report.per_case
        ],
    )


@router.get("/info", response_model=ModelInfoResponse)
def model_info(container: Annotated[Container, Depends(get_container)]) -> ModelInfoResponse:
    settings = container.settings
    return ModelInfoResponse(
        encoder_endpoint=settings.vertex_encoder_endpoint_id,
        encoder_model_path=container.encoder_model_path,
        reranker_endpoint=settings.vertex_reranker_endpoint_id,
        reranker_model_path=container.model_path,
        rerank_enabled=container.reranker_client is not None,
        search_enabled=settings.enable_search,
    )
