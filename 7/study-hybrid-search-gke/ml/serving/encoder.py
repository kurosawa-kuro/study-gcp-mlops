"""multilingual-e5-base encoder model + Vertex custom prediction routine.

ME5 models require the prompt prefix on every input:

* queries  → ``"query: ..."``
* passages → ``"passage: ..."``

Mixing them silently drops retrieval quality by several NDCG points. Keep the
helpers :func:`encode_query` / :func:`encode_passage` as the only entry points.

Heavy dependencies (``sentence_transformers``) are imported lazily inside
:meth:`E5Encoder.load`, so unit tests + composition roots that stub the
``model`` attribute do not need torch installed.

**過去事故の再発検知用ログ**:

* Phase 5 Run 6 で `AIP_STORAGE_URI` の trailing slash 依存バグが startup を 0
  ログで exit させた (`_download_artifact_dir`)。現在は artifact 探索の各段階
  (bucket / prefix / blob 件数 / download 進捗) を INFO で印字し、Pod logs を
  読めば即座に詰まり箇所を特定できる。
* env var 名 drift (AIP_STORAGE_URI ↔ STORAGE_URI) は startup の最初で全て
  echo するので `kubectl logs` で 1 行目を見るだけで判る。
* `load_encoder` の例外は traceback 付きで stderr に明示。KServe RawDeployment
  では stdout/stderr 両方が `kubectl logs` に流れるため二重出力は不要。
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ml.registry.artifact_store import GcsPrefix, download_file

# structlog ではなく stdlib で十分 (Vertex CPR / KServe RawDeployment 共に
# stdout 吸い上げ)。level と format は env で調整可能。
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=_LOG_LEVEL,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("encoder_server")

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
        logger.info("E5Encoder.load START model_dir=%s", model_dir)
        start = time.monotonic()
        from sentence_transformers import SentenceTransformer

        path = str(model_dir) if model_dir is not None else E5_MODEL_NAME
        logger.info("E5Encoder.load SentenceTransformer(%r) — this may take ~30s", path)
        model = SentenceTransformer(path)
        elapsed = time.monotonic() - start
        logger.info("E5Encoder.load OK elapsed=%.1fs", elapsed)
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
    """Download every blob under gcs_uri (directory prefix) into workdir/model/.

    Phase 5 Run 6 の事故対策: prefix.prefix は GcsPrefix.parse() で trailing `/`
    が剥がれる仕様なので、 self-contradict な `not endswith("/") → raise` は
    入れない。ここでは slash を補って list_blobs に渡し、blob name から同じ
    slash で相対パスを切り出す。
    """
    logger.info("_download_artifact_dir START gcs_uri=%s workdir=%s", gcs_uri, workdir)
    try:
        prefix = GcsPrefix.parse(gcs_uri)
    except Exception:
        logger.exception("GcsPrefix.parse FAILED gcs_uri=%r", gcs_uri)
        raise
    local_root = workdir / "model"
    local_root.mkdir(parents=True, exist_ok=True)
    logger.info(
        "_download_artifact_dir parsed bucket=%s prefix=%r local_root=%s",
        prefix.bucket,
        prefix.prefix,
        local_root,
    )
    from google.cloud import storage  # type: ignore[attr-defined]

    client = storage.Client()
    prefix_with_slash = f"{prefix.prefix}/" if prefix.prefix else ""
    downloaded = 0
    skipped_dirs = 0
    total_bytes = 0
    try:
        blobs = list(client.list_blobs(prefix.bucket, prefix=prefix_with_slash))
    except Exception:
        logger.exception("list_blobs FAILED bucket=%s prefix=%r", prefix.bucket, prefix_with_slash)
        raise
    logger.info(
        "_download_artifact_dir list_blobs OK count=%d bucket=%s prefix=%r",
        len(blobs),
        prefix.bucket,
        prefix_with_slash,
    )
    if not blobs:
        logger.error(
            "_download_artifact_dir NO BLOBS under gs://%s/%s — check placeholder vs "
            "`make deploy-kserve-models` status (AIP_STORAGE_URI should be a directory "
            "prefix with trailing `/`, uploaded by Model Registry). "
            "This is Phase 5 Run 6 class of fault.",
            prefix.bucket,
            prefix_with_slash,
        )
        raise RuntimeError(f"No blobs found under gs://{prefix.bucket}/{prefix_with_slash}")
    for blob in blobs:
        if blob.name.endswith("/"):
            skipped_dirs += 1
            continue
        rel = blob.name[len(prefix_with_slash) :] if prefix_with_slash else blob.name
        dest = local_root / rel
        try:
            download_file(f"gs://{prefix.bucket}/{blob.name}", dest)
        except Exception:
            logger.exception(
                "download_file FAILED blob=gs://%s/%s dest=%s",
                prefix.bucket,
                blob.name,
                dest,
            )
            raise
        downloaded += 1
        size = getattr(blob, "size", 0) or 0
        total_bytes += size
    logger.info(
        "_download_artifact_dir DONE downloaded=%d skipped_dirs=%d total_bytes=%d local_root=%s",
        downloaded,
        skipped_dirs,
        total_bytes,
        local_root,
    )
    return local_root


def _load_encoder() -> E5Encoder:
    storage_uri = os.getenv("AIP_STORAGE_URI", "").strip()
    predict_route = os.getenv("AIP_PREDICT_ROUTE", "/predict")
    health_route = os.getenv("AIP_HEALTH_ROUTE", "/health")
    http_port = os.getenv("AIP_HTTP_PORT", os.getenv("PORT", "8080"))
    logger.info(
        "encoder startup env: AIP_STORAGE_URI=%r AIP_PREDICT_ROUTE=%s AIP_HEALTH_ROUTE=%s "
        "AIP_HTTP_PORT=%s LOG_LEVEL=%s",
        storage_uri,
        predict_route,
        health_route,
        http_port,
        _LOG_LEVEL,
    )
    if not storage_uri:
        logger.error(
            "AIP_STORAGE_URI is EMPTY. KServe manifest (infra/manifests/kserve/encoder.yaml) "
            "must set `- name: AIP_STORAGE_URI` — not `STORAGE_URI` (Phase 5 Run 6 class)."
        )
        raise RuntimeError("AIP_STORAGE_URI is required")
    tmpdir = Path(tempfile.mkdtemp(prefix="encoder-model-"))
    logger.info("encoder startup tmpdir=%s", tmpdir)
    try:
        model_dir = _download_artifact_dir(storage_uri, tmpdir)
    except Exception:
        logger.exception(
            "encoder startup FAILED during artifact download. traceback:\n%s",
            traceback.format_exc(),
        )
        raise
    try:
        return E5Encoder.load(model_dir=model_dir)
    except Exception:
        logger.exception(
            "encoder startup FAILED during E5Encoder.load. model_dir=%s traceback:\n%s",
            model_dir,
            traceback.format_exc(),
        )
        raise


app = FastAPI(title="vertex-encoder-server")
app.state.encoder = None


@app.on_event("startup")
def _startup() -> None:
    logger.info("encoder app @on_event('startup') — loading encoder")
    start = time.monotonic()
    app.state.encoder = _load_encoder()
    logger.info(
        "encoder app startup complete elapsed=%.1fs model_name=%s",
        time.monotonic() - start,
        getattr(app.state.encoder, "model_name", "?"),
    )


@app.get(os.getenv("AIP_HEALTH_ROUTE", "/health"))
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(os.getenv("AIP_PREDICT_ROUTE", "/predict"), response_model=EncoderResponse)
def predict(request: EncoderRequest) -> EncoderResponse:
    encoder: E5Encoder | None = app.state.encoder
    if encoder is None:
        logger.error("predict called before encoder loaded (startup race?)")
        raise HTTPException(status_code=503, detail="encoder not loaded")
    instance_count = len(request.instances)
    queries = [item.text for item in request.instances if item.kind == "query"]
    passages = [item.text for item in request.instances if item.kind == "passage"]
    logger.info(
        "predict START instances=%d queries=%d passages=%d",
        instance_count,
        len(queries),
        len(passages),
    )
    start = time.monotonic()
    try:
        query_vectors = encoder.encode_queries(queries).tolist() if queries else []
        passage_vectors = encoder.encode_passages(passages).tolist() if passages else []
    except Exception:
        logger.exception(
            "predict FAILED during encode instances=%d q=%d p=%d traceback:\n%s",
            instance_count,
            len(queries),
            len(passages),
            traceback.format_exc(),
        )
        raise
    results: list[list[float]] = []
    query_index = 0
    passage_index = 0
    for item in request.instances:
        if item.kind == "query":
            results.append([float(v) for v in query_vectors[query_index]])
            query_index += 1
        else:
            results.append([float(v) for v in passage_vectors[passage_index]])
            passage_index += 1
    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "predict OK instances=%d results=%d dim=%d elapsed_ms=%.0f",
        instance_count,
        len(results),
        len(results[0]) if results else -1,
        elapsed_ms,
    )
    return EncoderResponse(predictions=results)


def main() -> None:
    import uvicorn

    port = int(os.getenv("AIP_HTTP_PORT", os.getenv("PORT", "8080")))
    logger.info("encoder uvicorn start host=0.0.0.0 port=%d", port)
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
