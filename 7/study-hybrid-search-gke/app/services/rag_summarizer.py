"""Phase 6 T6 — RAG summarizer service.

Wraps the existing hybrid search (``run_search``) with a generate step:
top-N ranked properties are handed to a :class:`Generator` along with the
user's query, and the generator emits a short natural-language summary /
recommendation. The underlying retrieval path (lexical + semantic + RRF
+ optional rerank) is unchanged — this service is additive.

Kept as a pure-logic service (no direct SDK imports) so unit tests can
plug in a stub ``Generator`` that returns a fixed string.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.domain.candidate import RankedCandidate
from app.services.protocols.generator import Generator


@dataclass(frozen=True)
class RagSummary:
    summary: str
    prompt_chars: int


def _format_context(ranked: list[RankedCandidate]) -> list[dict[str, object]]:
    """Serialize the ranked candidates into a Gemini-friendly JSON array.

    Only carries the columns that are useful for generation — full feature
    vectors are omitted to keep the prompt compact.
    """
    items: list[dict[str, object]] = []
    for item in ranked:
        props = item.candidate.property_features
        items.append(
            {
                "property_id": item.candidate.property_id,
                "final_rank": item.final_rank,
                "rent": props.get("rent"),
                "walk_min": props.get("walk_min"),
                "age_years": props.get("age_years"),
                "area_m2": props.get("area_m2"),
                "ctr": props.get("ctr"),
            }
        )
    return items


def build_prompt(*, query: str, ranked: list[RankedCandidate], top_n: int) -> str:
    context = _format_context(ranked[:top_n])
    return (
        f"ユーザのクエリ: {query}\n\n"
        f"候補物件 (上位 {len(context)} 件、JSON):\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "タスク:\n"
        "1. 候補物件の中からクエリに最も合う 3 件を選び、それぞれ 80 文字以内で紹介してください。\n"
        "2. 各紹介には `property_id` を含めてください。\n"
        "3. 候補外の物件を作らないでください (ハルシネーション禁止)。\n"
        "4. 出力は箇条書き (markdown) で。先頭に短い総評 (1 行) を添えてください。\n"
    )


class RagSummarizer:
    """Orchestrate: already-ranked candidates → Gemini summary."""

    def __init__(
        self,
        *,
        generator: Generator,
        default_top_n: int = 5,
        max_output_tokens: int = 512,
    ) -> None:
        self._generator = generator
        self._default_top_n = default_top_n
        self._max_output_tokens = max_output_tokens

    def summarize(
        self,
        *,
        query: str,
        ranked: list[RankedCandidate],
        top_n: int | None = None,
    ) -> RagSummary:
        effective_top_n = top_n if top_n is not None else self._default_top_n
        prompt = build_prompt(query=query, ranked=ranked, top_n=effective_top_n)
        text = self._generator.generate(prompt=prompt, max_output_tokens=self._max_output_tokens)
        return RagSummary(summary=text, prompt_chars=len(prompt))
