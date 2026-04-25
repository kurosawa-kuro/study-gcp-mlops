"""ML-facing dependency assembly.

This module owns optional PMLE enrichments wired into the API container.
All returned objects are startup singletons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.protocols.generator import Generator
from app.services.protocols.popularity_scorer import PopularityScorer
from app.services.rag_summarizer import RagSummarizer
from app.settings import ApiSettings


class MlBuilderContext(Protocol):
    _settings: ApiSettings
    _logger: Any

    def _bigquery(self) -> Any: ...


@dataclass(frozen=True)
class MlComponents:
    rag_summarizer: RagSummarizer | None
    popularity_scorer: PopularityScorer | None


class MlBuilder:
    def __init__(self, context: MlBuilderContext) -> None:
        self._context = context

    @property
    def _settings(self) -> ApiSettings:
        return self._context._settings

    @property
    def _logger(self) -> Any:
        return self._context._logger

    def build(self) -> MlComponents:
        return MlComponents(
            rag_summarizer=self.build_rag_summarizer(),
            popularity_scorer=self.build_popularity_scorer(),
        )

    def build_rag_summarizer(self) -> RagSummarizer | None:
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

    def build_popularity_scorer(self) -> PopularityScorer | None:
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
                client=self._context._bigquery(),
            )
        except Exception:
            self._logger.exception("Failed to initialize BQML popularity scorer")
            return None
