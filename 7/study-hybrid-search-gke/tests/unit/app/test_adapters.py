"""Tests for concrete adapters in app.adapters (Phase 6: KServe encoder/reranker)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.adapters import (
    KServeEncoder,
    KServeReranker,
    PubSubPublisher,
    create_retrain_queries,
)


def _fake_httpx_client(response_json: Any, *, status_code: int = 200) -> MagicMock:
    fake_response = MagicMock()
    fake_response.status_code = status_code
    fake_response.text = ""
    fake_response.json.return_value = response_json
    fake_response.raise_for_status.return_value = None
    client = MagicMock()
    client.post.return_value = fake_response
    return client


def test_create_retrain_queries_wires_bigquery_client() -> None:
    from app.services.adapters import BigQueryRetrainQueries

    fake_bq_client = MagicMock()
    fake_bq_client.query.return_value.result.return_value = iter([{"ts": None}])
    with patch("google.cloud.bigquery.Client", return_value=fake_bq_client) as client_cls:
        queries = create_retrain_queries(
            project_id="p",
            training_runs_table="p.m.training_runs",
        )
        queries.last_run_finished_at()

    client_cls.assert_called_once_with(project="p")
    assert isinstance(queries, BigQueryRetrainQueries)
    fake_bq_client.query.assert_called_once()
    assert "p.m.training_runs" in fake_bq_client.query.call_args.args[0]


def test_pubsub_publisher_publishes_json_bytes() -> None:
    fake_client = MagicMock()
    fake_client.topic_path.return_value = "projects/p/topics/retrain-trigger"
    fake_future = MagicMock()
    fake_client.publish.return_value = fake_future

    with patch("google.cloud.pubsub_v1.PublisherClient", return_value=fake_client):
        publisher = PubSubPublisher(project_id="p", topic="retrain-trigger")
        publisher.publish({"reasons": ["ndcg_drop=0.05>=0.03"], "日本語": "ok"})

    fake_client.topic_path.assert_called_once_with("p", "retrain-trigger")
    fake_client.publish.assert_called_once()
    call_args = fake_client.publish.call_args.args
    assert call_args[0] == "projects/p/topics/retrain-trigger"
    decoded = json.loads(call_args[1].decode("utf-8"))
    assert decoded == {"reasons": ["ndcg_drop=0.05>=0.03"], "日本語": "ok"}
    fake_future.result.assert_called_once()


def test_kserve_encoder_parses_embedding_dict_response_v1() -> None:
    fake_client = _fake_httpx_client({"predictions": [{"embedding": [0.1, 0.2, 0.3]}]})

    adapter = KServeEncoder(
        endpoint_url="http://property-encoder.kserve-inference.svc.cluster.local/v1/models/property-encoder:predict",
        client=fake_client,
    )
    vector = adapter.embed("赤羽駅徒歩10分", "query")

    fake_client.post.assert_called_once()
    sent_json = fake_client.post.call_args.kwargs["json"]
    # Phase 5 Run 6 の adapter バグ再発防止: text / kind は分離フィールドで送り、
    # ME5 の `query: ` prefix は server 側 E5Encoder が付与する契約。
    assert sent_json == {"instances": [{"text": "赤羽駅徒歩10分", "kind": "query"}]}
    assert vector == [0.1, 0.2, 0.3]
    assert "property-encoder" in adapter.endpoint_name


def test_kserve_reranker_parses_scalar_scores_v1() -> None:
    fake_client = _fake_httpx_client({"predictions": [0.9, 0.4, 0.1]})

    adapter = KServeReranker(
        endpoint_url="http://property-reranker.kserve-inference.svc.cluster.local/v1/models/property-reranker:predict",
        client=fake_client,
    )
    scores = adapter.predict([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    fake_client.post.assert_called_once()
    sent_json = fake_client.post.call_args.kwargs["json"]
    assert sent_json == {"instances": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]}
    assert scores == [0.9, 0.4, 0.1]
    assert "property-reranker" in adapter.model_path


def test_kserve_encoder_parses_v2_open_inference_response() -> None:
    fake_client = _fake_httpx_client({"outputs": [{"name": "embedding", "data": [[0.1, 0.2]]}]})

    adapter = KServeEncoder(endpoint_url="http://x/v1/models/m:predict", client=fake_client)
    vector = adapter.embed("q", "query")

    assert vector == [0.1, 0.2]


def test_kserve_reranker_predict_with_explain_via_predict_route() -> None:
    """No dedicated explain URL → POST to predict URL with parameters.explain=true.

    Matches the Phase 6 Vertex CPR reranker contract in ``ml/serving/reranker.py``
    where ``/predict`` accepts ``parameters.explain=True`` and returns both
    ``predictions`` and ``attributions`` in one round-trip.
    """
    fake_client = _fake_httpx_client(
        {
            "predictions": [0.9, 0.2],
            "attributions": [
                {"rent": 0.15, "walk_min": -0.05, "_baseline": 0.5},
                {"rent": -0.1, "walk_min": 0.08, "_baseline": 0.5},
            ],
        }
    )
    adapter = KServeReranker(
        endpoint_url="http://property-reranker.kserve-inference.svc.cluster.local/v1/models/property-reranker:predict",
        client=fake_client,
    )
    scores, attrs = adapter.predict_with_explain(
        [[1.0, 2.0], [3.0, 4.0]],
        feature_names=["rent", "walk_min"],
    )

    fake_client.post.assert_called_once()
    sent = fake_client.post.call_args.kwargs["json"]
    assert sent["instances"] == [[1.0, 2.0], [3.0, 4.0]]
    assert sent["parameters"] == {"explain": True, "feature_names": ["rent", "walk_min"]}
    assert scores == [0.9, 0.2]
    assert attrs == [
        {"rent": 0.15, "walk_min": -0.05, "_baseline": 0.5},
        {"rent": -0.1, "walk_min": 0.08, "_baseline": 0.5},
    ]


def test_kserve_reranker_predict_with_explain_via_dedicated_url() -> None:
    """When ``explain_url`` is set, the adapter calls it instead of predict URL.

    The dedicated route returns ``{attributions}`` only, so the adapter issues
    a second plain ``predict`` call to get scores. Tests verify both calls.
    """
    explain_response = _fake_httpx_client(
        {
            "attributions": [
                {"rent": 0.2, "_baseline": 0.5},
            ]
        }
    )
    # First POST = /explain (returns attributions), second POST = /predict (scores)
    explain_response.post.side_effect = [
        explain_response.post.return_value,
        _fake_httpx_client({"predictions": [0.77]}).post.return_value,
    ]
    adapter = KServeReranker(
        endpoint_url="http://r/v1/models/m:predict",
        explain_url="http://r/v1/models/m:explain",
        client=explain_response,
    )
    scores, attrs = adapter.predict_with_explain([[1.0, 2.0]], feature_names=["rent"])

    assert explain_response.post.call_count == 2
    first_call = explain_response.post.call_args_list[0]
    second_call = explain_response.post.call_args_list[1]
    # First call went to explain URL with {instances, feature_names}
    assert first_call.args[0] == "http://r/v1/models/m:explain"
    assert first_call.kwargs["json"] == {"instances": [[1.0, 2.0]], "feature_names": ["rent"]}
    # Second call went to predict URL (plain predict for scores)
    assert second_call.args[0] == "http://r/v1/models/m:predict"
    assert second_call.kwargs["json"] == {"instances": [[1.0, 2.0]]}
    assert scores == [0.77]
    assert attrs == [{"rent": 0.2, "_baseline": 0.5}]


def test_kserve_reranker_predict_with_explain_degrades_when_attrs_missing() -> None:
    """MLServer LightGBM runtime ignores ``parameters.explain=true`` and returns
    scores only. Adapter must not raise — it returns empty attribution dicts so
    the ``/search?explain=true`` path stays 200 with attributions=None per row.
    """
    fake_client = _fake_httpx_client({"predictions": [0.5, 0.6]})
    adapter = KServeReranker(endpoint_url="http://r/v1/models/m:predict", client=fake_client)
    scores, attrs = adapter.predict_with_explain(
        [[1.0, 2.0], [3.0, 4.0]],
        feature_names=["rent", "walk_min"],
    )

    assert scores == [0.5, 0.6]
    assert attrs == [{}, {}]  # empty per-instance dicts (graceful degradation)


def test_kserve_reranker_predict_with_explain_empty_instances_short_circuits() -> None:
    fake_client = _fake_httpx_client({})
    adapter = KServeReranker(endpoint_url="http://r/", client=fake_client)
    scores, attrs = adapter.predict_with_explain([], feature_names=[])
    assert scores == []
    assert attrs == []
    fake_client.post.assert_not_called()


def test_kserve_reranker_satisfies_reranker_explainer_protocol() -> None:
    """Structural check matching ``ranking.py``'s ``hasattr(reranker,
    'predict_with_explain')`` gate: KServeReranker must expose both ``predict``
    and ``predict_with_explain`` so services can opt into the explain path.
    """
    adapter = KServeReranker(endpoint_url="http://r/")
    assert callable(getattr(adapter, "predict", None))
    assert callable(getattr(adapter, "predict_with_explain", None))


def test_kserve_reranker_parses_v2_attributions_output() -> None:
    """V2 Open Inference: attributions come back as a named output with dict-rows data."""
    fake_client = _fake_httpx_client(
        {
            "outputs": [
                {"name": "predictions", "data": [0.5]},
                {
                    "name": "attributions",
                    "data": [{"rent": 0.3, "_baseline": 0.2}],
                },
            ]
        }
    )
    adapter = KServeReranker(endpoint_url="http://r/v2/models/m/infer", client=fake_client)
    scores, attrs = adapter.predict_with_explain([[1.0]], feature_names=["rent"])

    assert scores == [0.5]
    assert attrs == [{"rent": 0.3, "_baseline": 0.2}]
