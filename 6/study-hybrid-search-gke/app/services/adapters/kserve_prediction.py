"""KServe InferenceService adapters for encoder / reranker inference.

Both adapters call KServe via HTTP (cluster-local Service DNS). Authentication
is not required — NetworkPolicy restricts callers to the search-api Pod
within the cluster.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx


def _coerce_float_list(value: Any, *, field_name: str) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    raise TypeError(f"Expected list for {field_name}, got {type(value).__name__}")


def _extract_predictions(response_json: dict[str, Any]) -> list[Any]:
    """Extract predictions from a KServe v1/v2 response.

    KServe v1 Protocol: {"predictions": [...]}
    KServe v2 Protocol (Open Inference): {"outputs": [{"data": [...], ...}, ...]}
    """
    if "predictions" in response_json:
        return list(response_json["predictions"])
    if "outputs" in response_json:
        outputs = response_json["outputs"]
        if not outputs:
            return []
        # v2 returns a list of tensor outputs; take the first tensor's `data`
        first = outputs[0]
        if isinstance(first, dict) and "data" in first:
            data = first["data"]
            if isinstance(data, list):
                return data
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

    def embed(self, text: str, kind: Literal["query", "passage"]) -> list[float]:
        # Encoder server (ml/serving/encoder.py::EncoderInstance) は text と kind を
        # 分離フィールドで受け取り、server 側 E5Encoder が ME5 の `<kind>: ` prefix
        # を付与する契約。Phase 5 Run 6 で client 側 prefix 連結が 422 を誘発した
        # 痛み (docs/02_移行ロードマップ.md §1.1) から、ここでは prefix しない。
        payload = {"instances": [{"text": text.strip(), "kind": kind}]}
        response = self._client.post(self.endpoint_url, json=payload)
        response.raise_for_status()
        predictions = _extract_predictions(response.json())
        if not predictions:
            raise ValueError("KServe encoder returned no predictions")
        first = predictions[0]
        if isinstance(first, dict):
            for key in ("embedding", "embeddings", "values"):
                if key in first:
                    return _coerce_float_list(first[key], field_name=key)
            raise KeyError("KServe encoder response dict missing embedding payload")
        return _coerce_float_list(first, field_name="prediction")


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

    def predict(self, instances: list[list[float]]) -> list[float]:
        payload = {"instances": instances}
        response = self._client.post(self.endpoint_url, json=payload)
        response.raise_for_status()
        predictions = _extract_predictions(response.json())
        scores: list[float] = []
        for prediction in predictions:
            if isinstance(prediction, dict):
                for key in ("score", "prediction", "value"):
                    if key in prediction:
                        scores.append(float(prediction[key]))
                        break
                else:
                    raise KeyError("KServe reranker response dict missing score payload")
            else:
                scores.append(float(prediction))
        return scores
