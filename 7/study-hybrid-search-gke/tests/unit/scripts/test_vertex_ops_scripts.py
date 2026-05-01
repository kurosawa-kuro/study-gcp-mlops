from __future__ import annotations

from scripts.ops.vertex import feature_group, vector_search
from scripts.setup import backfill_vector_search_index


def test_vector_search_probe_vector_has_expected_shape() -> None:
    probe = vector_search._build_probe_vector()
    assert len(probe) == 768
    assert probe[0] == 1.0
    assert probe[1] == 0.5


def test_backfill_build_spec_reads_required_env(monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ID", "mlops-test")
    monkeypatch.setenv("VERTEX_LOCATION", "asia-northeast1")
    monkeypatch.setenv(
        "VERTEX_VECTOR_SEARCH_INDEX_RESOURCE_NAME",
        "projects/mlops-test/locations/asia-northeast1/indexes/123",
    )
    monkeypatch.setenv("VERTEX_VECTOR_SEARCH_UPSERT_BATCH_SIZE", "123")

    spec = backfill_vector_search_index.build_spec()

    assert spec.project_id == "mlops-test"
    assert spec.location == "asia-northeast1"
    assert spec.index_resource_name.endswith("/indexes/123")
    assert spec.embeddings_table == "mlops-test.feature_mart.property_embeddings"
    assert spec.batch_size == 123


def test_backfill_build_spec_rejects_non_int_batch_size(monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ID", "mlops-test")
    monkeypatch.setenv(
        "VERTEX_VECTOR_SEARCH_INDEX_RESOURCE_NAME",
        "projects/mlops-test/locations/asia-northeast1/indexes/123",
    )
    monkeypatch.setenv("VERTEX_VECTOR_SEARCH_UPSERT_BATCH_SIZE", "abc")

    try:
        backfill_vector_search_index.build_spec()
    except ValueError as exc:
        assert "must be int" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-int batch size")


def test_feature_group_prefers_feature_view_env_over_legacy_name(monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ID", "mlops-test")
    monkeypatch.setenv("VERTEX_LOCATION", "asia-northeast1")
    monkeypatch.setenv("VERTEX_FEATURE_ONLINE_STORE_ID", "store-a")
    monkeypatch.setenv("VERTEX_FEATURE_VIEW_ID", "view-a")
    monkeypatch.setenv("VERTEX_FEATURE_GROUP_ID", "legacy-group")
    monkeypatch.setenv("PROPERTY_ID", "p001")

    calls: list[object] = []

    class _AdminClient:
        def __init__(self, *, client_options):
            calls.append(("admin_init", client_options))

        def get_feature_online_store(self, *, name):
            calls.append(("get_store", name))
            return type(
                "Store",
                (),
                {
                    "dedicated_serving_endpoint": type(
                        "Endpoint", (), {"public_endpoint_domain_name": "featurestore.example"}
                    )()
                },
            )()

    class _DataKey:
        def __init__(self, *, key):
            self.key = key

    class _Request:
        def __init__(self, *, feature_view, data_key):
            self.feature_view = feature_view
            self.data_key = data_key

    class _ServingClient:
        def __init__(self, *, client_options):
            calls.append(("serving_init", client_options))

        def fetch_feature_values(self, *, request):
            calls.append(("fetch", request.feature_view, request.data_key.key))
            return type(
                "Response",
                (),
                {"key_values": type("KeyValues", (), {"features": [object()]})()},
            )()

    import sys
    from types import SimpleNamespace

    fake_module = SimpleNamespace(
        FeatureOnlineStoreAdminServiceClient=_AdminClient,
        FeatureOnlineStoreServiceClient=_ServingClient,
        FeatureViewDataKey=_DataKey,
        FetchFeatureValuesRequest=_Request,
    )
    monkeypatch.setitem(sys.modules, "google.cloud.aiplatform_v1beta1", fake_module)

    assert feature_group.main() == 0
    assert ("get_store", "projects/mlops-test/locations/asia-northeast1/featureOnlineStores/store-a") in calls
    assert (
        "fetch",
        "projects/mlops-test/locations/asia-northeast1/featureOnlineStores/store-a/featureViews/view-a",
        "p001",
    ) in calls

