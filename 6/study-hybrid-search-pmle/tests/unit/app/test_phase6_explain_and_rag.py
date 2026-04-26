"""Phase 6 T4 + T6 unit tests.

* **T4 (Explainable AI)** — ``run_search(want_explanations=True)`` returns
  attributions when the reranker satisfies ``RerankerExplainer``, and
  silently falls back to ``None`` otherwise.
* **T6 (RAG)** — ``RagSummarizer`` passes the ranked top-N to the injected
  ``Generator`` stub and returns the generator's text verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.candidate import Candidate, RankedCandidate
from app.services.rag_summarizer import RagSummarizer, build_prompt
from app.services.ranking import run_search

# --- Fakes mirroring tests/unit/app/test_ranking_service.py shape -----------


@dataclass
class _FakeRetriever:
    candidates: list[Candidate]

    def retrieve(
        self,
        *,
        query_text: str,
        query_vector: list[float],
        filters: dict[str, Any],
        top_k: int,
    ) -> list[Candidate]:
        return list(self.candidates)


@dataclass
class _FakePublisher:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def publish_candidates(
        self,
        *,
        request_id: str,
        candidates: list[Candidate],
        final_ranks: list[int],
        scores: list[float | None],
        model_path: str | None,
    ) -> None:
        self.calls.append(
            {
                "request_id": request_id,
                "final_ranks": list(final_ranks),
                "scores": list(scores),
                "model_path": model_path,
            }
        )


class _PlainReranker:
    """Only predict(); no predict_with_explain -> should fall back."""

    def predict(self, instances: list[list[float]]) -> list[float]:
        # higher score for later rows so final_rank flips vs lexical_rank
        return [float(idx) for idx in range(len(instances))]


class _ExplainReranker:
    """RerankerExplainer satisfier. Returns both scores + attributions."""

    def predict(self, instances: list[list[float]]) -> list[float]:
        return [float(idx) for idx in range(len(instances))]

    def predict_with_explain(
        self,
        instances: list[list[float]],
        feature_names: list[str],
    ) -> tuple[list[float], list[dict[str, float]]]:
        scores = [float(idx) for idx in range(len(instances))]
        attributions = [
            {name: 0.1 * (idx + 1) for name in feature_names} | {"_baseline": 0.0}
            for idx, _ in enumerate(instances)
        ]
        return scores, attributions


def _candidate(i: int) -> Candidate:
    return Candidate(
        property_id=f"P-{i:03d}",
        lexical_rank=i,
        semantic_rank=i,
        me5_score=0.9 - 0.05 * i,
        property_features={
            "rent": 100_000,
            "walk_min": 5,
            "age_years": 10,
            "area_m2": 30.0,
            "ctr": 0.1,
            "fav_rate": 0.02,
            "inquiry_rate": 0.01,
        },
    )


# --- T4: want_explanations=True + RerankerExplainer -------------------------


def test_run_search_returns_attributions_when_reranker_supports_explain() -> None:
    candidates = [_candidate(i) for i in range(1, 4)]
    retriever = _FakeRetriever(candidates=candidates)
    publisher = _FakePublisher()

    ranked = run_search(
        retriever=retriever,
        publisher=publisher,
        request_id="req-1",
        query_text="query",
        query_vector=[0.0] * 4,
        filters={},
        top_k=5,
        reranker=_ExplainReranker(),
        model_path="gs://models/v1",
        want_explanations=True,
    )

    assert len(ranked) == 3
    assert all(item.attributions is not None for item in ranked)
    # Feature names must include the 10 ranker columns (mirrors FEATURE_COLS_RANKER)
    any_row = next(iter(ranked)).attributions
    assert any_row is not None
    assert "rent" in any_row
    assert "me5_score" in any_row
    assert "_baseline" in any_row


# --- T4: want_explanations=True but reranker has no explain -> None ---------


def test_run_search_falls_back_to_no_attributions_when_reranker_lacks_explain() -> None:
    candidates = [_candidate(i) for i in range(1, 4)]
    retriever = _FakeRetriever(candidates=candidates)
    publisher = _FakePublisher()

    ranked = run_search(
        retriever=retriever,
        publisher=publisher,
        request_id="req-2",
        query_text="query",
        query_vector=[0.0] * 4,
        filters={},
        top_k=5,
        reranker=_PlainReranker(),
        model_path=None,
        want_explanations=True,
    )

    assert len(ranked) == 3
    assert all(item.attributions is None for item in ranked)


# --- T6: RagSummarizer -------------------------------------------------------


class _StubGenerator:
    def __init__(self, canned: str = "summary") -> None:
        self.canned = canned
        self.last_prompt: str | None = None

    def generate(self, *, prompt: str, max_output_tokens: int = 512) -> str:
        self.last_prompt = prompt
        return self.canned


def _ranked(n: int) -> list[RankedCandidate]:
    return [
        RankedCandidate(
            candidate=_candidate(i + 1),
            final_rank=i + 1,
            score=float(n - i),
            attributions=None,
        )
        for i in range(n)
    ]


def test_build_prompt_includes_query_and_property_ids() -> None:
    ranked = _ranked(3)
    prompt = build_prompt(query="渋谷 1LDK", ranked=ranked, top_n=2)
    assert "渋谷 1LDK" in prompt
    assert "P-001" in prompt
    assert "P-002" in prompt
    # top_n limits context — the 3rd candidate should not be in the prompt
    assert "P-003" not in prompt


def test_rag_summarizer_returns_generator_text() -> None:
    generator = _StubGenerator(canned="上位 2 件を紹介します…")
    summarizer = RagSummarizer(generator=generator, default_top_n=2, max_output_tokens=256)

    result = summarizer.summarize(query="q", ranked=_ranked(5))

    assert result.summary == "上位 2 件を紹介します…"
    assert generator.last_prompt is not None
    assert "P-001" in generator.last_prompt
    assert "P-002" in generator.last_prompt
    assert "P-003" not in generator.last_prompt  # top_n=2


def test_rag_summarizer_respects_explicit_top_n_override() -> None:
    generator = _StubGenerator()
    summarizer = RagSummarizer(generator=generator, default_top_n=2)

    summarizer.summarize(query="q", ranked=_ranked(5), top_n=4)

    assert generator.last_prompt is not None
    assert "P-004" in generator.last_prompt
    assert "P-005" not in generator.last_prompt
