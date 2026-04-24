"""FastAPI hybrid-search API — GKE Pod entrypoint.

The Pod keeps only retrieval / orchestration concerns. Query embeddings and
rerank scoring are delegated to KServe InferenceService (cluster-local HTTP)
when configured.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.middleware import RequestLoggingMiddleware
from app.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.services.adapters import (
    BigQueryCandidateRetriever,
    InMemoryTTLCacheStore,
    KServeEncoder,
    KServeReranker,
    MeilisearchLexical,
    NoopCacheStore,
    NoopFeedbackRecorder,
    NoopLexicalSearch,
    NoopRankingLogPublisher,
    PubSubFeedbackRecorder,
    PubSubPublisher,
    PubSubRankingLogPublisher,
    create_retrain_queries,
)
from app.services.config import ApiSettings
from app.services.protocols import (
    CacheStore,
    EncoderClient,
    FeedbackRecorder,
    LexicalSearchPort,
    PredictionPublisher,
    RankingLogPublisher,
    RerankerClient,
)
from app.services.ranking import normalize_search_cache_key, run_search
from app.services.retrain_policy import evaluate as evaluate_retrain
from ml.common.logging import configure_logging, get_logger


def _build_retrain_publisher(settings: ApiSettings) -> PredictionPublisher | None:
    if not settings.retrain_topic:
        return None
    return PubSubPublisher(project_id=settings.project_id, topic=settings.retrain_topic)


def _build_ranking_log_publisher(settings: ApiSettings) -> RankingLogPublisher:
    if not settings.ranking_log_topic:
        return NoopRankingLogPublisher()
    return PubSubRankingLogPublisher(
        project_id=settings.project_id, topic=settings.ranking_log_topic
    )


def _build_feedback_recorder(settings: ApiSettings) -> FeedbackRecorder:
    if not settings.feedback_topic:
        return NoopFeedbackRecorder()
    return PubSubFeedbackRecorder(project_id=settings.project_id, topic=settings.feedback_topic)


def _build_candidate_retriever(settings: ApiSettings) -> BigQueryCandidateRetriever:
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
    if settings.meili_base_url:
        lexical = MeilisearchLexical(
            base_url=settings.meili_base_url,
            index_name=settings.meili_index_name,
            api_key=settings.meili_api_key,
            master_key=settings.meili_master_key.get_secret_value(),
            require_identity_token=settings.meili_require_identity_token,
        )
    else:
        lexical = NoopLexicalSearch()

    return BigQueryCandidateRetriever(
        project_id=settings.project_id,
        lexical=lexical,
        embeddings_table=embeddings_table,
        features_table=features_table,
        properties_table=properties_table,
    )


def _build_search_cache(settings: ApiSettings) -> CacheStore:
    if settings.search_cache_ttl_seconds <= 0:
        return NoopCacheStore()
    return InMemoryTTLCacheStore(
        maxsize=settings.search_cache_maxsize,
        default_ttl_seconds=settings.search_cache_ttl_seconds,
    )


def _build_encoder_client(settings: ApiSettings) -> tuple[EncoderClient | None, str | None]:
    logger = get_logger("app")
    # Phase 5 Run 2 で endpoint_id 未設定により API が silently 起動不能だった
    # 再発防止: 設定の絶対値と判定結果を毎回明示する。
    logger.info(
        "build_encoder_client enable_search=%s kserve_encoder_url=%r timeout=%.1fs",
        settings.enable_search,
        settings.kserve_encoder_url,
        settings.kserve_predict_timeout_seconds,
    )
    if not settings.kserve_encoder_url:
        logger.warning(
            "ENABLE_SEARCH=true but KSERVE_ENCODER_URL is empty — encoder client DISABLED. "
            "Check infra/manifests/search-api/deployment.yaml env `KSERVE_ENCODER_URL`. "
            "Expected cluster-local: http://property-encoder.kserve-inference.svc.cluster.local/predict"
        )
        return None, None
    try:
        client = KServeEncoder(
            endpoint_url=settings.kserve_encoder_url,
            timeout_seconds=settings.kserve_predict_timeout_seconds,
        )
    except Exception:
        logger.exception(
            "Failed to initialize KServe encoder client url=%r",
            settings.kserve_encoder_url,
        )
        return None, None
    logger.info("encoder client READY endpoint_name=%s", client.endpoint_name)
    return client, client.endpoint_name


def _build_reranker_client(settings: ApiSettings) -> tuple[RerankerClient | None, str | None]:
    logger = get_logger("app")
    logger.info(
        "build_reranker_client enable_rerank=%s kserve_reranker_url=%r timeout=%.1fs",
        settings.enable_rerank,
        settings.kserve_reranker_url,
        settings.kserve_predict_timeout_seconds,
    )
    if not settings.enable_rerank:
        logger.info("ENABLE_RERANK=false — reranker client DISABLED (intentional)")
        return None, None
    if not settings.kserve_reranker_url:
        logger.warning(
            "ENABLE_RERANK=true but KSERVE_RERANKER_URL is empty — reranker client DISABLED. "
            "Expected cluster-local: "
            "http://property-reranker.kserve-inference.svc.cluster.local/v1/models/property-reranker:predict"
        )
        return None, None
    try:
        client = KServeReranker(
            endpoint_url=settings.kserve_reranker_url,
            timeout_seconds=settings.kserve_predict_timeout_seconds,
        )
    except Exception:
        logger.exception(
            "Failed to initialize KServe reranker client url=%r",
            settings.kserve_reranker_url,
        )
        return None, None
    logger.info("reranker client READY endpoint_name=%s", client.endpoint_name)
    return client, client.endpoint_name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    logger = get_logger("app")
    settings = ApiSettings()

    training_runs_table = (
        f"{settings.project_id}.{settings.bq_dataset_mlops}.{settings.bq_table_training_runs}"
    )

    app.state.retrain_trigger_publisher = _build_retrain_publisher(settings)
    app.state.retrain_queries = create_retrain_queries(
        project_id=settings.project_id,
        training_runs_table=training_runs_table,
    )

    if settings.enable_search:
        encoder_client, encoder_model_path = _build_encoder_client(settings)
        app.state.candidate_retriever = _build_candidate_retriever(settings)
        app.state.encoder_client = encoder_client
        app.state.encoder_model_path = encoder_model_path
    else:
        app.state.candidate_retriever = None
        app.state.encoder_client = None
        app.state.encoder_model_path = None

    reranker_client, model_path = _build_reranker_client(settings)
    app.state.reranker_client = reranker_client
    app.state.model_path = model_path

    app.state.ranking_log_publisher = _build_ranking_log_publisher(settings)
    app.state.feedback_recorder = _build_feedback_recorder(settings)
    app.state.search_cache = _build_search_cache(settings)
    app.state.settings = settings
    app.state.training_runs_table = training_runs_table
    logger.info(
        "Startup complete; search_enabled=%s rerank_enabled=%s model_path=%s",
        settings.enable_search,
        reranker_client is not None,
        model_path,
    )
    yield


def create_app() -> FastAPI:
    configure_logging()
    logger = get_logger("app")
    fastapi_app = FastAPI(title="gke+kserve-backed hybrid search API", lifespan=lifespan)
    app_root = Path(__file__).resolve().parent
    fastapi_app.mount("/static", StaticFiles(directory=str(app_root / "static")), name="static")
    templates = Jinja2Templates(directory=str(app_root / "templates"))
    fastapi_app.add_middleware(RequestLoggingMiddleware, logger=logger)

    @fastapi_app.get("/livez")
    @fastapi_app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @fastapi_app.get("/readyz")
    def readyz(request: Request) -> JSONResponse:
        retriever = getattr(request.app.state, "candidate_retriever", None)
        encoder_client = getattr(request.app.state, "encoder_client", None)
        if retriever is None or encoder_client is None:
            return JSONResponse({"status": "loading"}, status_code=503)
        reranker = getattr(request.app.state, "reranker_client", None)
        return JSONResponse(
            {
                "status": "ready",
                "search_enabled": True,
                "rerank_enabled": reranker is not None,
                "model_path": getattr(reranker, "model_path", None),
            }
        )

    @fastapi_app.get("/")
    def ui(request: Request) -> object:
        search_payload = {
            "query": "渋谷 1LDK",
            "filters": {
                "max_rent": 220000,
                "layout": "1LDK",
                "max_walk_min": 12,
                "pet_ok": True,
                "max_age": 20,
            },
            "top_k": 20,
        }
        feedback_payload = {
            "request_id": "demo-request-id",
            "property_id": "1001",
            "action": "click",
        }
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "active": "predict",
                "search_payload": search_payload,
                "feedback_payload": feedback_payload,
            },
        )

    @fastapi_app.get("/metrics")
    def metrics_ui(request: Request) -> object:
        settings: ApiSettings = request.app.state.settings
        payload = {
            "service": "phase6-gke-kserve-api",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "project_id": settings.project_id,
            "enable_search": settings.enable_search,
            "enable_rerank": settings.enable_rerank,
            "kserve_encoder_url": settings.kserve_encoder_url,
            "kserve_reranker_url": settings.kserve_reranker_url,
            "model_path": getattr(request.app.state, "model_path", None),
        }
        return templates.TemplateResponse(
            request,
            "metrics.html",
            {"active": "metrics", "metrics": payload},
        )

    @fastapi_app.get("/data")
    def data_ui(request: Request) -> object:
        rows = [
            {"key": "search_payload", "value": '{"query":"渋谷 1LDK","top_k":20}'},
            {"key": "feedback_payload", "value": '{"request_id":"...","action":"click"}'},
            {"key": "kserve_encoder", "value": "settings.kserve_encoder_url"},
            {"key": "kserve_reranker", "value": "settings.kserve_reranker_url"},
        ]
        return templates.TemplateResponse(
            request,
            "data.html",
            {"active": "data", "columns": ["key", "value"], "rows": rows, "total": len(rows)},
        )

    @fastapi_app.post("/search", response_model=SearchResponse)
    def search(req: SearchRequest, request: Request) -> SearchResponse | JSONResponse:
        retriever = getattr(request.app.state, "candidate_retriever", None)
        encoder_client = getattr(request.app.state, "encoder_client", None)
        if retriever is None or encoder_client is None:
            return JSONResponse(
                {"detail": "/search disabled (enable_search=False or KServe encoder missing)"},
                status_code=503,
            )
        request_id = cast(str, getattr(request.state, "request_id", uuid.uuid4().hex))
        settings: ApiSettings = request.app.state.settings
        search_cache: CacheStore = request.app.state.search_cache
        cache_key = normalize_search_cache_key(
            query=req.query,
            filters=req.filters.model_dump(),
            top_k=req.top_k,
        )
        cached = search_cache.get(cache_key)
        if cached is not None:
            cached_results = [SearchResultItem.model_validate(item) for item in cached["results"]]
            return SearchResponse(
                request_id=request_id,
                results=cached_results,
                model_path=cached.get("model_path"),
            )

        query_vector = encoder_client.embed(req.query, "query")

        publisher: RankingLogPublisher = request.app.state.ranking_log_publisher
        reranker = getattr(request.app.state, "reranker_client", None)
        model_path = getattr(reranker, "model_path", getattr(request.app.state, "model_path", None))
        ranked = run_search(
            retriever=retriever,
            publisher=publisher,
            request_id=request_id,
            query_text=req.query,
            query_vector=query_vector,
            filters=req.filters.model_dump(),
            top_k=req.top_k,
            reranker=reranker,
            model_path=model_path,
        )

        results = [
            SearchResultItem(
                property_id=item.candidate.property_id,
                final_rank=item.final_rank,
                lexical_rank=item.candidate.lexical_rank,
                semantic_rank=item.candidate.semantic_rank,
                me5_score=item.candidate.me5_score,
                score=item.score,
            )
            for item in ranked
        ]
        search_cache.set(
            cache_key,
            {
                "results": [r.model_dump() for r in results],
                "model_path": model_path,
            },
            settings.search_cache_ttl_seconds,
        )
        return SearchResponse(request_id=request_id, results=results, model_path=model_path)

    @fastapi_app.post("/feedback", response_model=FeedbackResponse)
    def feedback(req: FeedbackRequest, request: Request) -> FeedbackResponse:
        recorder: FeedbackRecorder = request.app.state.feedback_recorder
        try:
            recorder.record(
                request_id=req.request_id,
                property_id=req.property_id,
                action=req.action,
            )
        except Exception:
            get_logger("app").exception("Feedback publish failed — continuing")
            return FeedbackResponse(accepted=False)
        return FeedbackResponse(accepted=True)

    @fastapi_app.post("/jobs/check-retrain")
    def check_retrain(request: Request) -> JSONResponse:
        """Evaluate OR-conditions, publish retrain-trigger if any fires, return decision."""
        queries = request.app.state.retrain_queries
        decision = evaluate_retrain(queries)
        response: dict[str, object] = {
            "should_retrain": decision.should_retrain,
            "reasons": decision.reasons,
            "feedback_rows_since_last": decision.feedback_rows_since_last,
            "ndcg_current": decision.ndcg_current,
            "ndcg_week_ago": decision.ndcg_week_ago,
            "last_run_finished_at": (
                decision.last_run_finished_at.isoformat() if decision.last_run_finished_at else None
            ),
        }

        if decision.should_retrain:
            trigger: PredictionPublisher | None = getattr(
                request.app.state, "retrain_trigger_publisher", None
            )
            if trigger is not None:
                try:
                    trigger.publish({"reasons": decision.reasons})
                    response["published"] = True
                except Exception:
                    get_logger("app").exception("Failed to publish retrain-trigger")
                    response["published"] = False
        return JSONResponse(response)

    return fastapi_app


app = create_app()
