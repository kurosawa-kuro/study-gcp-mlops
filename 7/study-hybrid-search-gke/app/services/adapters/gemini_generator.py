"""Gemini (Vertex AI Model Garden) adapter for the ``Generator`` Port.

Phase 6 T6 — uses ``vertexai.generative_models.GenerativeModel`` which is
already bundled in ``google-cloud-aiplatform`` (Phase 5 dependency). No
new Python package is required.

System instructions are hard-coded to the real-estate ranking domain so
Gemini stays on-topic and refuses to hallucinate properties that are not
in the passed-in context. The concrete prompt assembly lives in
:class:`app.services.rag_summarizer.RagSummarizer`; this adapter's only
job is "turn a prompt string into a string response".
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("app.gemini_generator")


DEFAULT_SYSTEM_INSTRUCTION = (
    "あなたは不動産検索サイトのアシスタントです。"
    "渡された物件 JSON 配列の中からのみ回答してください。"
    "配列に無い物件や事実は生成しないでください。"
    "日本語で簡潔に、ユーザのクエリに関連する物件を優先して説明してください。"
)


class GeminiGenerator:
    """Thin wrapper over ``vertexai.generative_models.GenerativeModel``."""

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        model_name: str = "gemini-1.5-flash",
        system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
        temperature: float = 0.2,
        client: Any | None = None,
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model_name = model_name
        self._system_instruction = system_instruction
        self._temperature = temperature
        self._client = client  # injected in tests
        logger.info(
            "GeminiGenerator init project=%s location=%s model=%s",
            project_id,
            location,
            model_name,
        )

    def prepare(self) -> None:
        """Eagerly construct the underlying ``GenerativeModel``.

        Phase A-4 — composition root calls this once at startup so the
        SDK initialization (``vertexai.init`` + ``GenerativeModel``) happens
        deterministically rather than on the first request. Failures
        propagate so the composition root can downgrade ``rag_service`` to
        ``None`` and surface the failure in startup logs.
        """
        self._model()

    def _model(self) -> Any:
        if self._client is not None:
            return self._client
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=self._project_id, location=self._location)
        self._client = GenerativeModel(
            model_name=self._model_name,
            system_instruction=[self._system_instruction],
        )
        return self._client

    def generate(self, *, prompt: str, max_output_tokens: int = 512) -> str:
        from vertexai.generative_models import GenerationConfig

        model = self._model()
        logger.info(
            "gemini.generate model=%s prompt_chars=%d max_tokens=%d",
            self._model_name,
            len(prompt),
            max_output_tokens,
        )
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=self._temperature,
                max_output_tokens=max_output_tokens,
            ),
        )
        text = getattr(response, "text", None)
        if text is None:
            candidates = getattr(response, "candidates", [])
            if candidates:
                parts = getattr(candidates[0].content, "parts", [])
                text = "".join(getattr(p, "text", "") for p in parts)
        if not text:
            raise RuntimeError("Gemini returned empty response")
        return str(text)
