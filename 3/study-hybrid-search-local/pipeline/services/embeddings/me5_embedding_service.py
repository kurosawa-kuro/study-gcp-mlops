from __future__ import annotations

import hashlib
import os
import threading
from typing import Iterable


class Embedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._backend = "fallback"
        self._model = None

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(model_name)
            self._backend = "sentence-transformers"
        except Exception:  # noqa: BLE001
            self._backend = "fallback"

    @property
    def backend(self) -> str:
        return self._backend

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self._backend == "sentence-transformers" and self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return [list(map(float, row)) for row in vectors]

        # Fallback: deterministic hash embedding (keeps pipeline runnable offline)
        return [fallback_embedding(text) for text in texts]


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                model_name = os.getenv("ME5_MODEL_NAME", "intfloat/multilingual-e5-large")
                _embedder = Embedder(model_name)
    return _embedder


def normalize(vec: list[float]) -> list[float]:
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def fallback_embedding(text: str, dim: int = 128) -> list[float]:
    values: list[float] = []
    seed = text.encode("utf-8")

    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        for b in seed:
            values.append((b / 127.5) - 1.0)
            if len(values) == dim:
                break

    return normalize(values)


def encode_queries(queries: Iterable[str]) -> list[list[float]]:
    texts = [f"query: {q}" for q in queries]
    return get_embedder().encode(texts)


def encode_passages(passages: Iterable[str]) -> list[list[float]]:
    texts = [f"passage: {p}" for p in passages]
    return get_embedder().encode(texts)
