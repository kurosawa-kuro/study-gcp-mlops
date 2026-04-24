"""Port for LLM text generation.

Phase 6 T6 — keeps the Gemini SDK isolated behind a Protocol so the RAG
service stays testable without GCP credentials. Expected implementation
lives in :mod:`app.services.adapters.gemini_generator`.
"""

from __future__ import annotations

from typing import Protocol


class Generator(Protocol):
    """Generate free-text from a prompt + optional structured context."""

    def generate(self, *, prompt: str, max_output_tokens: int = 512) -> str: ...
