"""``RankingLogPublisher`` Port — per-request ranking log emission."""

from __future__ import annotations

from typing import Protocol

from app.services.protocols.candidate_retriever import Candidate


class RankingLogPublisher(Protocol):
    """Writes one row per retrieved candidate to the ranking log."""

    def publish_candidates(
        self,
        *,
        request_id: str,
        candidates: list[Candidate],
        final_ranks: list[int],
        scores: list[float | None],
        model_path: str | None,
    ) -> None: ...
