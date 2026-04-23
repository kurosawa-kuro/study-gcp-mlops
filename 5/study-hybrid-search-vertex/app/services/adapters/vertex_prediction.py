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
        logger.info(
            "reranker.predict endpoint=%s batch=%d dims=%d",
            self.endpoint_name,
            len(instances),
            len(instances[0]) if instances else -1,
        )
        try:
            response = self._endpoint.predict(instances=instances)
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


# expose for upstream log filter configuration
_ = traceback  # keep import explicit even if unused in body
