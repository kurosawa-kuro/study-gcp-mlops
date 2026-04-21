"""multilingual-e5-base encoder model + Vertex custom prediction routine.

ME5 models require the prompt prefix on every input:

* queries  → ``"query: ..."``
* passages → ``"passage: ..."``

Mixing them silently drops retrieval quality by several NDCG points. Keep the
helpers :func:`encode_query` / :func:`encode_passage` as the only entry points.

Heavy dependencies (``sentence_transformers``) are imported lazily inside
:meth:`E5Encoder.load`, so unit tests + composition roots that stub the
``model`` attribute do not need torch installed.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ml.registry.artifact_store import GcsPrefix, download_file

E5_MODEL_NAME: str = "intfloat/multilingual-e5-base"
E5_VECTOR_DIM: int = 768

QUERY_PREFIX: str = "query: "
PASSAGE_PREFIX: str = "passage: "


@dataclass
class E5Encoder:
    """Thin wrapper around a sentence-transformers model with ME5 prefixes."""

    model: Any
    model_name: str = E5_MODEL_NAME
    vector_dim: int = E5_VECTOR_DIM

    @classmethod
    def load(cls, *, model_dir: Path | None = None) -> E5Encoder:
        """Instantiate a real sentence-transformers encoder from ``model_dir``."""
        from sentence_transformers import SentenceTransformer

        path = str(model_dir) if model_dir is not None else E5_MODEL_NAME
        model = SentenceTransformer(path)
        return cls(model=model)

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(vectors, dtype=float)

    def encode_queries(self, queries: list[str]) -> np.ndarray:
        return self._encode([QUERY_PREFIX + q for q in queries])

    def encode_passages(self, passages: list[str]) -> np.ndarray:
        return self._encode([PASSAGE_PREFIX + p for p in passages])


def encode_query(encoder: E5Encoder, query: str) -> np.ndarray:
    return np.asarray(encoder.encode_queries([query])[0])


def encode_passage(encoder: E5Encoder, passage: str) -> np.ndarray:
    return np.asarray(encoder.encode_passages([passage])[0])


class EncoderInstance(BaseModel):
    text: str = Field(min_length=1)
    kind: str = Field(pattern="^(query|passage)$")


class EncoderRequest(BaseModel):
    instances: list[EncoderInstance]


class EncoderResponse(BaseModel):
    predictions: list[list[float]]


def _download_artifact_dir(gcs_uri: str, workdir: Path) -> Path:
    prefix = GcsPrefix.parse(gcs_uri)
    local_root = workdir / "model"
    local_root.mkdir(parents=True, exist_ok=True)
    if prefix.prefix and not prefix.prefix.endswith("/"):
        raise RuntimeError("AIP_STORAGE_URI must point to a directory prefix")
    from google.cloud import storage

    client = storage.Client()
    for blob in client.list_blobs(prefix.bucket, prefix=prefix.prefix):
        if blob.name.endswith("/"):
            continue
        rel = blob.name[len(prefix.prefix) :].lstrip("/") if prefix.prefix else blob.name
        download_file(f"gs://{prefix.bucket}/{blob.name}", local_root / rel)
    return local_root


def _load_encoder() -> E5Encoder:
    storage_uri = os.getenv("AIP_STORAGE_URI", "").strip()
    if not storage_uri:
        raise RuntimeError("AIP_STORAGE_URI is required")
    tmpdir = Path(tempfile.mkdtemp(prefix="encoder-model-"))
    model_dir = _download_artifact_dir(storage_uri, tmpdir)
    return E5Encoder.load(model_dir=model_dir)


app = FastAPI(title="vertex-encoder-server")
app.state.encoder = None


@app.on_event("startup")
def _startup() -> None:
    app.state.encoder = _load_encoder()


@app.get(os.getenv("AIP_HEALTH_ROUTE", "/health"))
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(os.getenv("AIP_PREDICT_ROUTE", "/predict"), response_model=EncoderResponse)
def predict(request: EncoderRequest) -> EncoderResponse:
    encoder: E5Encoder | None = app.state.encoder
    if encoder is None:
        raise HTTPException(status_code=503, detail="encoder not loaded")
    queries = [item.text for item in request.instances if item.kind == "query"]
    passages = [item.text for item in request.instances if item.kind == "passage"]
    results: list[list[float]] = []
    query_vectors = encoder.encode_queries(queries).tolist() if queries else []
    passage_vectors = encoder.encode_passages(passages).tolist() if passages else []
    query_index = 0
    passage_index = 0
    for item in request.instances:
        if item.kind == "query":
            results.append([float(v) for v in query_vectors[query_index]])
            query_index += 1
        else:
            results.append([float(v) for v in passage_vectors[passage_index]])
            passage_index += 1
    return EncoderResponse(predictions=results)


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("AIP_HTTP_PORT", os.getenv("PORT", "8080"))),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
