from __future__ import annotations

from typing import Protocol


class EmbeddingPort(Protocol):
    def embed_query(self, text: str) -> list[float]:
        ...
