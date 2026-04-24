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


def _extract_attributions(
    response_json: dict[str, Any],
    n_instances: int,
) -> list[dict[str, float]] | None:
    """Parse per-instance attribution dicts from a reranker response.

    Supported response shapes (in priority order):
      1. Phase 6 Vertex CPR server — ``{"predictions": [...], "attributions": [...]}``
         or ``{"attributions": [...]}`` (from dedicated ``/explain`` route).
      2. KServe v2 — ``{"outputs": [..., {"name": "attributions", "data": [...]}]}``.

    Returns ``None`` when the response carries no attribution payload (e.g. the
    operator is still running the MLServer LightGBM runtime, which ignores
    ``parameters.explain=true``). Caller can treat ``None`` as "explain not
    supported by the deployed container — see docs/02_移行ロードマップ.md §4.2 T4".
    """
    attrs = response_json.get("attributions")
    if isinstance(attrs, list) and len(attrs) == n_instances:
        return [
            {str(k): float(v) for k, v in row.items()} for row in attrs if isinstance(row, dict)
        ] or None
    outputs = response_json.get("outputs")
    if isinstance(outputs, list):
        for out in outputs:
            if isinstance(out, dict) and out.get("name") == "attributions":
                data = out.get("data")
                if isinstance(data, list) and len(data) == n_instances:
                    return [
                        {str(k): float(v) for k, v in row.items()}
                        for row in data
                        if isinstance(row, dict)
                    ] or None
    return None


class KServeReranker:
    """Adapter over a KServe InferenceService that returns one score per row.

    Supports both plain scoring (``predict``) and scoring with per-instance
    TreeSHAP attributions (``predict_with_explain``, Phase 6 T4). The explain
    path POSTs to ``endpoint_url`` with ``parameters.explain=true``; when the
    deployed container is the Phase 6 Vertex CPR reranker (or a future KServe
    runtime that honors the same parameter), the response carries
    ``attributions`` alongside ``predictions``. If the container ignores the
    parameter (e.g. stock MLServer LightGBM runtime) we log a warning and fall
    back to returning scores-only + empty attribution dicts so callers degrade
    gracefully instead of 500.

    Operators that deploy a dedicated ``/explain`` route (separate URL) can
    pass ``explain_url`` at construction time; the adapter will prefer that URL
    when attributions are requested.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        explain_url: str | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url.strip()
        if not self.endpoint_url:
            raise ValueError("KServeReranker requires a non-empty endpoint_url")
        self.endpoint_name = self.endpoint_url
        self.model_path = self.endpoint_url
        # Treat whitespace-only strings as "no explain URL configured" so
        # misconfigured ConfigMap values (accidental trailing newline, tab, etc.)
        # degrade to the parameters.explain=true fallback instead of producing
        # a bogus request to an empty URL.
        _explain = explain_url.strip() if explain_url else ""
        self.explain_url = _explain if _explain else None
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)
        logger.info(
            "KServeReranker init endpoint_url=%s explain_url=%s timeout=%.1fs (expect "
            "path `/v1/models/property-reranker:predict` for MLServer LightGBM runtime; "
            "explain requires Vertex CPR container or equivalent)",
            self.endpoint_url,
            self.explain_url or "(fallback: parameters.explain=true on predict URL)",
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

    def predict_with_explain(
        self,
        instances: list[list[float]],
        feature_names: list[str],
    ) -> tuple[list[float], list[dict[str, float]]]:
        """Score + TreeSHAP attribution in a single round-trip.

        Dispatches via ``explain_url`` (dedicated ``/explain`` route) when the
        adapter was constructed with one, otherwise POSTs to ``endpoint_url``
        with ``parameters.explain=true`` + ``feature_names`` (matching the
        Phase 6 Vertex CPR reranker contract in ``ml/serving/reranker.py``).

        Degradation policy: if the deployed container silently ignores the
        explain parameter and returns only scores, we emit a warning and
        return empty ``{}`` attribution dicts for every instance. The caller
        (``app.services.ranking``) surfaces these as ``attributions=None``
        per row, so the ``/search?explain=true`` response stays 200 with
        attributions missing rather than 500-ing on the client.
        """
        if not instances:
            logger.warning("reranker.predict_with_explain called with empty instances")
            return [], []
        url = self.explain_url or self.endpoint_url
        use_explain_route = self.explain_url is not None
        if use_explain_route:
            # Dedicated /explain route (Phase 6 Vertex CPR custom server): body
            # is {instances, feature_names}, response is {attributions}. We
            # still need scores, so issue a separate predict call afterwards
            # when attributions come back.
            payload: dict[str, Any] = {"instances": instances, "feature_names": feature_names}
        else:
            # /predict with explain param: single round-trip, response carries
            # both predictions and attributions.
            payload = {
                "instances": instances,
                "parameters": {"explain": True, "feature_names": feature_names},
            }
        logger.info(
            "reranker.predict_with_explain START url=%s batch=%d use_explain_route=%s",
            url,
            len(instances),
            use_explain_route,
        )
        start = time.monotonic()
        try:
            response = self._client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.exception(
                "reranker.predict_with_explain HTTPError url=%s batch=%d exc_type=%s msg=%s\n%s",
                url,
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
                "reranker.predict_with_explain HTTP %d url=%s batch=%d elapsed_ms=%.0f body[:500]=%r",
                response.status_code,
                url,
                len(instances),
                elapsed_ms,
                body_preview,
            )
        response.raise_for_status()
        response_json = response.json()
        attributions = _extract_attributions(response_json, len(instances))
        if use_explain_route:
            # /explain gave us only attributions; fetch scores with a regular
            # predict call. Cheap because it runs against the same booster.
            scores = self.predict(instances)
        else:
            try:
                predictions = _extract_predictions(response_json)
            except KeyError:
                logger.error(
                    "reranker.predict_with_explain response missing predictions. summary=%s",
                    _response_summary(response_json),
                )
                raise
            scores = []
            for p in predictions:
                if isinstance(p, dict):
                    raw = p.get("score", p.get("value", 0.0))
                    scores.append(float(raw) if raw is not None else 0.0)
                else:
                    scores.append(float(p))
        if attributions is None:
            logger.warning(
                "reranker.predict_with_explain url=%s batch=%d: response carries no "
                "attribution payload — deployed container likely ignores explain. "
                "Returning empty dicts. Switch reranker container to the Phase 6 Vertex "
                "CPR image (ml/serving/reranker.py) or wire `explain_url` to a route "
                "that returns {attributions}. summary=%s",
                url,
                len(instances),
                _response_summary(response_json),
            )
            attributions = [{} for _ in instances]
        logger.info(
            "reranker.predict_with_explain OK url=%s batch=%d scores=%d attrs=%d elapsed_ms=%.0f",
            url,
            len(instances),
            len(scores),
            len(attributions),
            elapsed_ms,
        )
        return scores, attributions
