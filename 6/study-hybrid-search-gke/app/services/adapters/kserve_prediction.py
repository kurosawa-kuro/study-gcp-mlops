"""KServe InferenceService adapters for encoder / reranker inference.

Both adapters call KServe via HTTP (cluster-local Service DNS). Authentication
is not required — NetworkPolicy restricts callers to the search-api Pod
within the cluster.

過去事故の再発検知用に、構造化ログを大量に仕込んである。主要な着火点:

* Phase 5 Run 6 — encoder が `{"text": "query: ..."}` の 1 フィールド payload で
  422 (`Field required: kind`) を返した事故。payload shape / status code /
  response body の先頭を log するので、同じ contract drift を瞬時に特定できる。
* KServe URL path drift (§1.2) — encoder は `/predict` (Vertex CPR 規約) を
  listen、reranker は `/v1/models/property-reranker:predict` (KServe v1 規約) を
  listen。init 時に URL を echo して差異を可視化。
* `KServeEncoder response dict missing embedding payload` — response JSON が
  dict の場合に embedding key が見つからないと raise。その際は response dict
  の keys を stderr に出すので、runtime の v1/v2 protocol 切替えにも強い。
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Literal

import httpx

logger = logging.getLogger("app.kserve_prediction")


def _coerce_float_list(value: Any, *, field_name: str) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    raise TypeError(f"Expected list for {field_name}, got {type(value).__name__}")


def _response_summary(response_json: Any) -> str:
    """Short text summary for logs (never dump whole body — may be huge embedding)."""
    if isinstance(response_json, dict):
        keys = sorted(response_json.keys())
        preds = response_json.get("predictions")
        outputs = response_json.get("outputs")
        n_preds = len(preds) if isinstance(preds, list) else "N/A"
        n_outputs = len(outputs) if isinstance(outputs, list) else "N/A"
        return f"dict keys={keys} predictions.len={n_preds} outputs.len={n_outputs}"
    return f"{type(response_json).__name__}"


def _extract_predictions(response_json: dict[str, Any]) -> list[Any]:
    """Extract predictions from a KServe v1/v2 response.

    KServe v1 Protocol: {"predictions": [...]}
    KServe v2 Protocol (Open Inference): {"outputs": [{"data": [...], ...}, ...]}
    """
    if "predictions" in response_json:
        preds = list(response_json["predictions"])
        logger.info("kserve.response protocol=v1 predictions.len=%d", len(preds))
        return preds
    if "outputs" in response_json:
        outputs = response_json["outputs"]
        if not outputs:
            logger.warning("kserve.response protocol=v2 outputs=[] (empty body)")
            return []
        first = outputs[0]
        if isinstance(first, dict) and "data" in first:
            data = first["data"]
            if isinstance(data, list):
                logger.info(
                    "kserve.response protocol=v2 outputs[0].name=%s data.len=%d",
                    first.get("name", "?"),
                    len(data),
                )
                return data
    logger.error(
        "kserve.response shape UNKNOWN — cannot extract predictions. summary=%s",
        _response_summary(response_json),
    )
    raise KeyError("KServe response missing 'predictions' (v1) or 'outputs' (v2)")


class KServeEncoder:
    """Adapter over a KServe InferenceService that returns one embedding per text."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url.strip()
        if not self.endpoint_url:
            raise ValueError("KServeEncoder requires a non-empty endpoint_url")
        self.endpoint_name = self.endpoint_url
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)
        logger.info(
            "KServeEncoder init endpoint_url=%s timeout=%.1fs (expect path `/predict` "
            "for Vertex CPR encoder server)",
            self.endpoint_url,
            timeout_seconds,
        )

    def embed(self, text: str, kind: Literal["query", "passage"]) -> list[float]:
        # Encoder server (ml/serving/encoder.py::EncoderInstance) は text と kind を
        # 分離フィールドで受け取り、server 側 E5Encoder が ME5 の `<kind>: ` prefix
        # を付与する契約。Phase 5 Run 6 で client 側 prefix 連結が 422 を誘発した
        # 痛み (docs/02_移行ロードマップ.md §1.1) から、ここでは prefix しない。
        text_stripped = text.strip()
        payload = {"instances": [{"text": text_stripped, "kind": kind}]}
        logger.info(
            "encoder.embed START endpoint=%s kind=%s text_len=%d",
            self.endpoint_url,
            kind,
            len(text_stripped),
        )
        start = time.monotonic()
        try:
            response = self._client.post(self.endpoint_url, json=payload)
        except httpx.HTTPError as exc:
            logger.exception(
                "encoder.embed HTTPError endpoint=%s kind=%s exc_type=%s msg=%s",
                self.endpoint_url,
                kind,
                type(exc).__name__,
                str(exc),
            )
            raise
        elapsed_ms = (time.monotonic() - start) * 1000
        if response.status_code >= 400:
            # Phase 5 Run 6 の 422 再発を即座に検知するため、status + body 先頭を dump
            body_preview = response.text[:500]
            logger.error(
                "encoder.embed HTTP %d endpoint=%s kind=%s elapsed_ms=%.0f body[:500]=%r",
                response.status_code,
                self.endpoint_url,
                kind,
                elapsed_ms,
                body_preview,
            )
        response.raise_for_status()
        response_json = response.json()
        predictions = _extract_predictions(response_json)
        if not predictions:
            logger.error(
                "encoder.embed empty predictions endpoint=%s kind=%s summary=%s",
                self.endpoint_url,
                kind,
                _response_summary(response_json),
            )
            raise ValueError("KServe encoder returned no predictions")
        first = predictions[0]
        if isinstance(first, dict):
            for key in ("embedding", "embeddings", "values"):
                if key in first:
                    vec = _coerce_float_list(first[key], field_name=key)
                    logger.info(
                        "encoder.embed OK endpoint=%s kind=%s dim=%d elapsed_ms=%.0f via_key=%s",
                        self.endpoint_url,
                        kind,
                        len(vec),
                        elapsed_ms,
                        key,
                    )
                    return vec
            logger.error(
                "encoder response dict missing embedding payload. "
                "available_keys=%s (expected one of: embedding / embeddings / values)",
                sorted(first.keys()),
            )
            raise KeyError("KServe encoder response dict missing embedding payload")
        vec = _coerce_float_list(first, field_name="prediction")
        logger.info(
            "encoder.embed OK endpoint=%s kind=%s dim=%d elapsed_ms=%.0f via=bare_list",
            self.endpoint_url,
            kind,
            len(vec),
            elapsed_ms,
        )
        return vec


class KServeReranker:
    """Adapter over a KServe InferenceService that returns one score per row."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url.strip()
        if not self.endpoint_url:
            raise ValueError("KServeReranker requires a non-empty endpoint_url")
        self.endpoint_name = self.endpoint_url
        self.model_path = self.endpoint_url
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)
        logger.info(
            "KServeReranker init endpoint_url=%s timeout=%.1fs (expect path "
            "`/v1/models/property-reranker:predict` for MLServer LightGBM runtime)",
            self.endpoint_url,
            timeout_seconds,
        )

    def predict(self, instances: list[list[float]]) -> list[float]:
        if not instances:
            logger.warning("reranker.predict called with empty instances")
            return []
        payload = {"instances": instances}
        logger.info(
            "reranker.predict START endpoint=%s batch=%d dims=%d",
            self.endpoint_url,
            len(instances),
            len(instances[0]) if instances else -1,
        )
        start = time.monotonic()
        try:
            response = self._client.post(self.endpoint_url, json=payload)
        except httpx.HTTPError as exc:
            logger.exception(
                "reranker.predict HTTPError endpoint=%s batch=%d exc_type=%s msg=%s\n%s",
                self.endpoint_url,
                len(instances),
                type(exc).__name__,
                str(exc),
                traceback.format_exc(),
            )
            raise
        elapsed_ms = (time.monotonic() - start) * 1000
        if response.status_code >= 400:
            body_preview = response.text[:500]
            logger.error(
                "reranker.predict HTTP %d endpoint=%s batch=%d elapsed_ms=%.0f body[:500]=%r "
                "head_instance=%s",
                response.status_code,
                self.endpoint_url,
                len(instances),
                elapsed_ms,
                body_preview,
                instances[0][:5] if instances and instances[0] else [],
            )
        response.raise_for_status()
        response_json = response.json()
        predictions = _extract_predictions(response_json)
        scores: list[float] = []
        for idx, prediction in enumerate(predictions):
            if isinstance(prediction, dict):
                for key in ("score", "prediction", "value"):
                    if key in prediction:
                        scores.append(float(prediction[key]))
                        break
                else:
                    logger.error(
                        "reranker response[%d] dict missing score payload. "
                        "available_keys=%s (expected one of: score / prediction / value)",
                        idx,
                        sorted(prediction.keys()),
                    )
                    raise KeyError("KServe reranker response dict missing score payload")
            else:
                scores.append(float(prediction))
        logger.info(
            "reranker.predict OK endpoint=%s batch=%d scores=%d elapsed_ms=%.0f "
            "score_range=[%.4f, %.4f]",
            self.endpoint_url,
            len(instances),
            len(scores),
            elapsed_ms,
            min(scores) if scores else 0.0,
            max(scores) if scores else 0.0,
        )
        return scores
