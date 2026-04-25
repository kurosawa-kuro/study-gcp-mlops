"""``SearchService`` — orchestrates /search and /rag retrieval.

Pure-logic service depending only on Ports. The HTTP layer
(`app/api/handlers/search_handler.py`) builds a :class:`SearchInput` from
the FastAPI request, delegates to ``SearchService.search``, then maps the
returned :class:`SearchOutput` back to a Pydantic response.

Phase D-1 lifted the orchestration that was inlined in
``app/main.py:481-591`` into this class. The pure orchestration
``run_search`` from ``app/services/ranking.py`` is reused here.
"""

from __future__ import annotations

from app.domain.candidate import RankedCandidate
from app.domain.search import SearchFilters, SearchInput, SearchOutput, SearchResultItem
from app.services.protocols.cache_store import CacheStore
from app.services.protocols.candidate_retriever import CandidateRetriever
from app.services.protocols.encoder_client import EncoderClient
from app.services.protocols.popularity_scorer import PopularityScorer
from app.services.protocols.ranking_log_publisher import RankingLogPublisher
from app.services.protocols.reranker_client import RerankerClient
from app.services.ranking import normalize_search_cache_key, run_search
from ml.common.logging import get_logger

logger = get_logger("app.search_service")


class SearchServiceUnavailable(Exception):
    """Raised when the SearchService cannot fulfill a request because a
    required port (encoder, retriever) is unavailable. The HTTP layer
    converts to 503.
    """


class SearchService:
    """Hybrid-search use case (inbound port equivalent).

    All collaborators are injected — composition root constructs the
    service once at startup. ``cache``, ``reranker``, ``popularity_scorer``
    are optional; ``None`` means the corresponding feature is disabled.
    """

    def __init__(
        self,
        *,
        retriever_default: CandidateRetriever | None,
        retriever_alt: CandidateRetriever | None,
        encoder: EncoderClient | None,
        publisher: RankingLogPublisher,
        reranker: RerankerClient | None = None,
        popularity_scorer: PopularityScorer | None = None,
        cache: CacheStore | None = None,
        cache_ttl_seconds: int = 120,
    ) -> None:
        self._retriever_default = retriever_default
        self._retriever_alt = retriever_alt
        self._encoder = encoder
        self._publisher = publisher
        self._reranker = reranker
        self._popularity_scorer = popularity_scorer
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    @property
    def reranker_model_path(self) -> str | None:
        return getattr(self._reranker, "model_path", None)

    def _pick_retriever(self, lexical_backend: str) -> CandidateRetriever | None:
        if lexical_backend == "agent_builder":
            return self._retriever_alt
        return self._retriever_default

    def search(self, *, request_id: str, input: SearchInput) -> SearchOutput:
        """Execute one /search call.

        Raises :class:`SearchServiceUnavailable` when the selected lexical
        backend or the encoder is missing — the HTTP handler maps to 503.
        """
        retriever = self._pick_retriever(input.lexical_backend)
        if retriever is None:
            raise SearchServiceUnavailable(
                f"/search?lexical={input.lexical_backend} unavailable "
                "(retriever not configured)"
            )
        if self._encoder is None:
            raise SearchServiceUnavailable(
                "/search disabled (enable_search=False or encoder missing)"
            )

        cache_key = normalize_search_cache_key(
            query=input.query,
            # Include the lexical backend in the cache key so meili /
            # agent_builder responses do not shadow each other.
            filters={**dict(input.filters), "_lexical": input.lexical_backend},
            top_k=input.top_k,
        )

        # Phase 6 T4 — explain bypasses cache; attributions must be per-request.
        if self._cache is not None and not input.explain:
            cached = self._cache.get(cache_key)
            if cached is not None:
                cached_items = [
                    SearchResultItem(**dict(item)) for item in cached["results"]
                ]
                return SearchOutput(
                    request_id=request_id,
                    items=cached_items,
                    model_path=cached.get("model_path"),
                    ranked=[],
                )

        query_vector = self._encoder.embed(input.query, "query")
        ranked: list[RankedCandidate] = run_search(
            retriever=retriever,
            publisher=self._publisher,
            request_id=request_id,
            query_text=input.query,
            query_vector=query_vector,
            filters=dict(input.filters),
            top_k=input.top_k,
            reranker=self._reranker,
            model_path=self.reranker_model_path,
            want_explanations=input.explain,
        )

        # Phase 6 T1 — BQML auxiliary popularity scoring (opt-in).
        popularity_map: dict[str, float] = {}
        if self._popularity_scorer is not None and ranked:
            try:
                popularity_map = self._popularity_scorer.score(
                    [item.candidate.property_id for item in ranked]
                )
            except Exception:
                logger.exception("BQML popularity scorer failed — continuing")

        items = [
            SearchResultItem(
                property_id=item.candidate.property_id,
                final_rank=item.final_rank,
                lexical_rank=item.candidate.lexical_rank,
                semantic_rank=item.candidate.semantic_rank,
                me5_score=item.candidate.me5_score,
                score=item.score,
                attributions=item.attributions,
                popularity_score=popularity_map.get(item.candidate.property_id),
            )
            for item in ranked
        ]
        model_path = self.reranker_model_path

        if self._cache is not None and not input.explain:
            # Persist only non-explain responses so subsequent /search calls
            # without ``?explain=true`` continue to hit the cache.
            self._cache.set(
                cache_key,
                {
                    "results": [
                        {
                            "property_id": it.property_id,
                            "final_rank": it.final_rank,
                            "lexical_rank": it.lexical_rank,
                            "semantic_rank": it.semantic_rank,
                            "me5_score": it.me5_score,
                            "score": it.score,
                            "attributions": it.attributions,
                            "popularity_score": it.popularity_score,
                        }
                        for it in items
                    ],
                    "model_path": model_path,
                },
                self._cache_ttl_seconds,
            )

        return SearchOutput(
            request_id=request_id,
            items=items,
            model_path=model_path,
            ranked=ranked,
        )


# ----------------------------------------------------------------------- helpers


def filters_from_dict(raw: dict[str, object]) -> SearchFilters:
    """Coerce a Pydantic ``model_dump()`` dict to ``SearchFilters`` TypedDict.

    TypedDict has no runtime enforcement, but explicit construction keeps
    Mypy happy and surfaces unexpected keys.
    """
    out: SearchFilters = {}
    if "max_rent" in raw and raw["max_rent"] is not None:
        out["max_rent"] = int(raw["max_rent"])  # type: ignore[arg-type]
    if "layout" in raw and raw["layout"] is not None:
        out["layout"] = str(raw["layout"])
    if "max_walk_min" in raw and raw["max_walk_min"] is not None:
        out["max_walk_min"] = int(raw["max_walk_min"])  # type: ignore[arg-type]
    if "pet_ok" in raw and raw["pet_ok"] is not None:
        out["pet_ok"] = bool(raw["pet_ok"])
    if "max_age" in raw and raw["max_age"] is not None:
        out["max_age"] = int(raw["max_age"])  # type: ignore[arg-type]
    return out
