"""Search-facing dependency assembly.

Scope:
- singleton adapters built once at startup
- helper selection rules for lexical / semantic wiring
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.adapters import (
    BigQueryCandidateRetriever,
    BigQueryFeatureFetcher,
    FeatureOnlineStoreFetcher,
    KServeEncoder,
    KServeReranker,
    MeilisearchLexical,
    VertexVectorSearchSemanticSearch,
)
from app.services.noop_adapters import NoopLexicalSearch
from app.services.protocols import CandidateRetriever, EncoderClient, LexicalSearchPort
from app.services.protocols.feature_fetcher import FeatureFetcher
from app.services.protocols.reranker_client import RerankerClient
from app.services.protocols.semantic_search import SemanticSearchPort
from app.settings import ApiSettings

EXPECTED_KSERVE_ENCODER_URL = (
    "http://property-encoder-predictor.kserve-inference.svc.cluster.local/predict"
)
EXPECTED_KSERVE_RERANKER_URL = (
    "http://property-reranker-predictor.kserve-inference.svc.cluster.local"
    "/v2/models/property-reranker/infer"
)


def _resolve_index_endpoint_name(*, project_id: str, location: str, endpoint_id: str) -> str:
    """Accept either a bare endpoint ID or a fully-qualified resource name."""
    if endpoint_id.startswith("projects/"):
        return endpoint_id
    return f"projects/{project_id}/locations/{location}/indexEndpoints/{endpoint_id}"


class SearchBuilderContext(Protocol):
    _settings: ApiSettings
    _logger: Any

    def _bigquery(self) -> Any: ...


@dataclass(frozen=True)
class SearchComponents:
    candidate_retriever: CandidateRetriever | None
    encoder_client: EncoderClient | None
    encoder_model_path: str | None
    reranker_client: RerankerClient | None
    model_path: str | None


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
        if settings.feature_flags.enable_search:
            encoder_client, encoder_model_path = self.build_encoder_client()
            candidate_retriever = self.build_candidate_retriever()
        else:
            encoder_client = None
            encoder_model_path = None
            candidate_retriever = None
        reranker_client, model_path = self.build_reranker_client()
        return SearchComponents(
            candidate_retriever=candidate_retriever,
            encoder_client=encoder_client,
            encoder_model_path=encoder_model_path,
            reranker_client=reranker_client,
            model_path=model_path,
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
        semantic = self._resolve_semantic_search()
        return BigQueryCandidateRetriever(
            project_id=settings.project_id,
            lexical=lexical,
            embeddings_table=embeddings_table,
            features_table=features_table,
            properties_table=properties_table,
            semantic=semantic,
            client=self._context._bigquery(),
        )

    def resolve_feature_fetcher(self) -> FeatureFetcher | None:
        """Build a ``FeatureFetcher`` based on ``settings.feature_fetcher_backend``.

        PR-2 keeps this as a public ``resolve_*`` (no leading underscore) so
        PR-4 can call it from the reranker wiring without breaking the
        ``SearchBuilderContext`` Protocol. PR-2 itself does NOT plug the
        result into ``Container`` — defaults stay observable-equivalent.

        Returns ``None`` when:
        - ``feature_fetcher_backend == "online_store"`` but the FeatureView
          / endpoint config is empty (Wave 2 待ち)、または
        - ``bq`` 選択時で ``features_table`` 解決に必要な settings が空。
        Callers treat ``None`` as "feature fetch disabled" and fall back to
        whatever inline mechanism existed previously.
        """
        settings = self._settings
        if settings.feature_fetcher_backend == "online_store":
            store_id = settings.vertex_feature_online_store_id
            view_id = settings.vertex_feature_view_id
            endpoint = settings.vertex_feature_online_store_endpoint
            if not store_id or not view_id or not endpoint:
                self._logger.warning(
                    "FEATURE_FETCHER_BACKEND=online_store but "
                    "VERTEX_FEATURE_ONLINE_STORE_ID=%r / VERTEX_FEATURE_VIEW_ID=%r / "
                    "VERTEX_FEATURE_ONLINE_STORE_ENDPOINT=%r is empty — disabling "
                    "Feature Online Store fetcher (Wave 2 で provision 後に再有効化).",
                    store_id,
                    view_id,
                    endpoint,
                )
                return None
            feature_view = (
                f"projects/{settings.project_id}/locations/{settings.vertex_location}"
                f"/featureOnlineStores/{store_id}/featureViews/{view_id}"
            )
            self._logger.info(
                "feature fetcher = online_store feature_view=%s endpoint=%s",
                feature_view,
                endpoint,
            )
            return FeatureOnlineStoreFetcher(
                feature_view=feature_view,
                endpoint_resolver=lambda: endpoint,
            )
        # default = bq → BigQueryFeatureFetcher with the BQ client used elsewhere.
        features_table = (
            f"{settings.project_id}.{settings.bq_dataset_feature_mart}."
            f"{settings.bq_table_property_features_daily}"
        )
        if not features_table.strip("."):
            return None
        return BigQueryFeatureFetcher(
            features_table=features_table,
            client=self._context._bigquery(),
        )

    def _resolve_semantic_search(self) -> SemanticSearchPort | None:
        """Choose ``SemanticSearchPort`` impl based on ``settings.semantic_backend``.

        Default (``bq``): return ``None`` so ``BigQueryCandidateRetriever``
        constructs its built-in ``BigQuerySemanticSearch`` and existing
        Phase 4 / Phase 5 default behaviour is preserved unchanged
        (Strangler 原則 — see Phase 7 ``docs/tasks/TASKS_ROADMAP.md`` §2.1).

        ``vertex_vector_search``: build ``VertexVectorSearchSemanticSearch``
        using the configured Index Endpoint resource. If endpoint /
        deployed-index ID is not yet provisioned (Wave 2 待ち)、warn loudly
        and fall back to the BigQuery default so the app stays serviceable.
        """
        settings = self._settings
        if settings.semantic_backend != "vertex_vector_search":
            return None

        endpoint_id = settings.vertex_vector_search_index_endpoint_id
        deployed_id = settings.vertex_vector_search_deployed_index_id
        if not endpoint_id or not deployed_id:
            self._logger.warning(
                "SEMANTIC_BACKEND=vertex_vector_search but "
                "VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID=%r / "
                "VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID=%r is empty — "
                "falling back to BigQuery VECTOR_SEARCH (Phase 4 default). "
                "Provision Wave 2 Terraform vector_search module to enable.",
                endpoint_id,
                deployed_id,
            )
            return None

        endpoint_name = _resolve_index_endpoint_name(
            project_id=settings.project_id,
            location=settings.vertex_location,
            endpoint_id=endpoint_id,
        )
        self._logger.info(
            "semantic backend = vertex_vector_search endpoint=%s deployed_index_id=%s",
            endpoint_name,
            deployed_id,
        )
        return VertexVectorSearchSemanticSearch(
            index_endpoint_name=endpoint_name,
            deployed_index_id=deployed_id,
            project=settings.project_id,
            location=settings.vertex_location,
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
                impersonate_service_account=settings.meili_impersonate_service_account,
                token_audience=settings.meili_token_audience,
            )
        return NoopLexicalSearch()

    def build_encoder_client(self) -> tuple[EncoderClient | None, str | None]:
        settings = self._settings
        flags = settings.feature_flags
        kserve = settings.kserve
        self._logger.info(
            "build_encoder_client enable_search=%s kserve_encoder_url=%r timeout=%.1fs",
            flags.enable_search,
            kserve.encoder_url,
            kserve.predict_timeout_seconds,
        )
        if not kserve.encoder_url:
            self._logger.warning(
                "ENABLE_SEARCH=true but KSERVE_ENCODER_URL is empty — encoder client DISABLED. "
                "Check infra/manifests/search-api/deployment.yaml env `KSERVE_ENCODER_URL`. "
                "Expected cluster-local: %s",
                EXPECTED_KSERVE_ENCODER_URL,
            )
            return None, None
        try:
            client = KServeEncoder(
                endpoint_url=kserve.encoder_url,
                timeout_seconds=kserve.predict_timeout_seconds,
            )
        except Exception:
            self._logger.exception(
                "Failed to initialize KServe encoder client url=%r",
                kserve.encoder_url,
            )
            return None, None
        self._logger.info("encoder client READY endpoint_name=%s", client.endpoint_name)
        return client, client.endpoint_name

    def build_reranker_client(self) -> tuple[RerankerClient | None, str | None]:
        settings = self._settings
        flags = settings.feature_flags
        kserve = settings.kserve
        self._logger.info(
            "build_reranker_client enable_rerank=%s kserve_reranker_url=%r timeout=%.1fs",
            flags.enable_rerank,
            kserve.reranker_url,
            kserve.predict_timeout_seconds,
        )
        if not flags.enable_rerank:
            self._logger.info("ENABLE_RERANK=false — reranker client DISABLED (intentional)")
            return None, None
        if not kserve.reranker_url:
            self._logger.warning(
                "ENABLE_RERANK=true but KSERVE_RERANKER_URL is empty — reranker client DISABLED. "
                "Expected cluster-local: %s",
                EXPECTED_KSERVE_RERANKER_URL,
            )
            return None, None
        try:
            client = KServeReranker(
                endpoint_url=kserve.reranker_url,
                explain_url=kserve.reranker_explain_url or None,
                timeout_seconds=kserve.predict_timeout_seconds,
            )
        except Exception:
            self._logger.exception(
                "Failed to initialize KServe reranker client url=%r",
                kserve.reranker_url,
            )
            return None, None
        self._logger.info("reranker client READY endpoint_name=%s", client.endpoint_name)
        return client, client.endpoint_name
