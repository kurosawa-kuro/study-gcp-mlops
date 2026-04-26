"""Vertex AI Endpoint adapters for encoder / reranker inference."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Literal

logger = logging.getLogger("app.vertex_prediction")


def _normalize_endpoint_name(*, project_id: str, location: str, endpoint_id: str) -> str:
    endpoint_id = endpoint_id.strip()
    if endpoint_id.startswith("projects/"):
        return endpoint_id
    return f"projects/{project_id}/locations/{location}/endpoints/{endpoint_id}"


def _create_endpoint(*, project_id: str, location: str, endpoint_name: str) -> Any:
    from google.cloud import aiplatform

    aiplatform.init(project=project_id, location=location)
    return aiplatform.Endpoint(endpoint_name)


def _coerce_float_list(value: Any, *, field_name: str) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    raise TypeError(f"Expected list for {field_name}, got {type(value).__name__}")


class VertexEndpointEncoder:
    """Adapter over a Vertex AI Endpoint that returns one embedding per text."""

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        endpoint_id: str,
        timeout_seconds: float = 30.0,
        endpoint: Any | None = None,
    ) -> None:
        _ = timeout_seconds
        self.endpoint_name = _normalize_endpoint_name(
            project_id=project_id,
            location=location,
            endpoint_id=endpoint_id,
        )
        logger.info("VertexEndpointEncoder init endpoint_name=%s", self.endpoint_name)
        self._endpoint = endpoint or _create_endpoint(
            project_id=project_id,
            location=location,
            endpoint_name=self.endpoint_name,
        )

    def embed(self, text: str, kind: Literal["query", "passage"]) -> list[float]:
        # Vertex encoder server (ml/serving/encoder.py::EncoderInstance) expects
        # separate `text` and `kind` fields; the server applies the ME5
        # `<kind>:` prefix internally via E5Encoder. Do not pre-prefix here.
        payload = {"text": text.strip(), "kind": kind}
        logger.info(
            "encoder.predict endpoint=%s kind=%s text_len=%d",
            self.endpoint_name,
            kind,
            len(payload["text"]),
        )
        try:
            response = self._endpoint.predict(instances=[payload])
        except Exception:
            logger.exception(
                "encoder.predict FAILED endpoint=%s payload_keys=%s",
                self.endpoint_name,
                list(payload.keys()),
            )
            raise
        predictions = list(getattr(response, "predictions", []))
        logger.info(
            "encoder.predict OK endpoint=%s predictions_count=%d",
            self.endpoint_name,
            len(predictions),
        )
        if not predictions:
            logger.error("encoder returned no predictions endpoint=%s", self.endpoint_name)
            raise ValueError("Vertex encoder returned no predictions")
        first = predictions[0]
        if isinstance(first, dict):
            for key in ("embedding", "embeddings", "values"):
                if key in first:
                    vec = _coerce_float_list(first[key], field_name=key)
                    logger.info("encoder embedding shape=%d via key=%s", len(vec), key)
                    return vec
            logger.error(
                "encoder response dict missing embedding payload keys=%s",
                list(first.keys()),
            )
            raise KeyError("Vertex encoder response dict missing embedding payload")
        vec = _coerce_float_list(first, field_name="prediction")
        logger.info("encoder embedding shape=%d via bare list", len(vec))
        return vec


class VertexEndpointReranker:
    """Adapter over a Vertex AI Endpoint that returns one score per row."""

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        endpoint_id: str,
        timeout_seconds: float = 30.0,
        endpoint: Any | None = None,
    ) -> None:
        _ = timeout_seconds
        self.endpoint_name = _normalize_endpoint_name(
            project_id=project_id,
            location=location,
            endpoint_id=endpoint_id,
        )
        logger.info("VertexEndpointReranker init endpoint_name=%s", self.endpoint_name)
        self.model_path = self.endpoint_name
        self._endpoint = endpoint or _create_endpoint(
            project_id=project_id,
            location=location,
            endpoint_name=self.endpoint_name,
        )

    def predict(self, instances: list[list[float]]) -> list[float]:
        scores, _ = self._predict(instances, parameters=None)
        return scores

    def predict_with_explain(
        self,
        instances: list[list[float]],
        feature_names: list[str],
    ) -> tuple[list[float], list[dict[str, float]]]:
        """Phase 6 T4 — scores + TreeSHAP attributions in one round-trip.

        Forwards ``parameters.explain=true`` + ``feature_names`` through the
        Vertex ``Endpoint.predict`` body. The server (ml/serving/reranker.py)
        inspects ``parameters`` and, when ``explain`` is truthy, appends a
        parallel ``attributions`` array to the response.
        """
        scores, attributions = self._predict(
            instances,
            parameters={"explain": True, "feature_names": feature_names},
        )
        if attributions is None:
            # Server returned predictions but no attributions — treat as an
            # integration bug rather than silently degrading to empty dicts.
            raise RuntimeError(
                "reranker.predict_with_explain: server did not return attributions; "
                "check that ml/serving/reranker.py is deployed with the Phase 6 T4 build"
            )
        return scores, attributions

    def _predict(
        self,
        instances: list[list[float]],
        parameters: dict[str, Any] | None,
    ) -> tuple[list[float], list[dict[str, float]] | None]:
        logger.info(
            "reranker.predict endpoint=%s batch=%d dims=%d explain=%s",
            self.endpoint_name,
            len(instances),
            len(instances[0]) if instances else -1,
            bool(parameters and parameters.get("explain")),
        )
        try:
            if parameters is None:
                response = self._endpoint.predict(instances=instances)
            else:
                response = self._endpoint.predict(
                    instances=instances,
                    parameters=parameters,
                )
        except Exception:
            logger.exception(
                "reranker.predict FAILED endpoint=%s batch=%d head=%s",
                self.endpoint_name,
                len(instances),
                instances[:1] if instances else [],
            )
            raise
        predictions = list(getattr(response, "predictions", []))
        logger.info(
            "reranker.predict OK endpoint=%s predictions=%d",
            self.endpoint_name,
            len(predictions),
        )
        scores = _extract_scores(predictions)
        attributions = _extract_attributions(response, len(scores))
        return scores, attributions


def _extract_scores(predictions: list[Any]) -> list[float]:
    scores: list[float] = []
    for prediction in predictions:
        if isinstance(prediction, dict):
            for key in ("score", "prediction", "value"):
                if key in prediction:
                    scores.append(float(prediction[key]))
                    break
            else:
                logger.error(
                    "reranker response dict missing score payload keys=%s",
                    list(prediction.keys()),
                )
                raise KeyError("Vertex reranker response dict missing score payload")
        else:
            scores.append(float(prediction))
    return scores


def _extract_attributions(response: Any, expected_len: int) -> list[dict[str, float]] | None:
    """Pull ``attributions`` from the Vertex ``Prediction`` response if present.

    The Vertex SDK forwards unknown top-level response keys verbatim (the
    ``attributions`` field is added by our ml/serving/reranker.py when
    ``parameters.explain=true``). Returns ``None`` if the response does not
    carry an attributions payload.
    """
    raw = getattr(response, "attributions", None)
    # Recent SDK versions bury non-standard fields under ``_prediction_response``
    # instead of surfacing them as attributes; cover both.
    if raw is None:
        doc = getattr(response, "_prediction_response", None)
        if isinstance(doc, dict):
            raw = doc.get("attributions")
    if raw is None:
        return None
    attributions: list[dict[str, float]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise TypeError(
                f"Vertex reranker attributions entry is not a dict: {type(entry).__name__}"
            )
        attributions.append({str(k): float(v) for k, v in entry.items()})
    if attributions and len(attributions) != expected_len:
        logger.warning(
            "reranker attributions length mismatch scores=%d attributions=%d",
            expected_len,
            len(attributions),
        )
    return attributions


# expose for upstream log filter configuration
_ = traceback  # keep import explicit even if unused in body
