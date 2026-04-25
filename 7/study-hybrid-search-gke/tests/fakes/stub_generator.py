"""Fixed-text ``Generator`` stub for Phase 6 T6 RAG tests."""

from __future__ import annotations

from app.services.protocols.generator import Generator


class StubGenerator(Generator):
    def __init__(self, *, response: str = "stub-summary") -> None:
        self._response = response
        self.calls: list[_GenerateCall] = []

    def generate(self, *, prompt: str, max_output_tokens: int = 512) -> str:
        self.calls.append(_GenerateCall(prompt=prompt, max_output_tokens=max_output_tokens))
        return self._response


class _GenerateCall:
    __slots__ = ("prompt", "max_output_tokens")

    def __init__(self, *, prompt: str, max_output_tokens: int) -> None:
        self.prompt = prompt
        self.max_output_tokens = max_output_tokens
