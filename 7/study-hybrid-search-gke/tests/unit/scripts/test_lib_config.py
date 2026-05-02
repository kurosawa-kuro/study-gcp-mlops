"""Pin scripts/lib/config.py — single source for ConfigMap schema.

Phase 7 W2-5 で `_run_overlay_configmap` と `sync_configmap.py` の独立な
キー手書きが drift して rollout が壊れた。本テストは:

1. CONFIGMAP_KEYS が deployment.yaml が要求する 10 キー全てを覆う
2. generate_configmap_data() の出力が all-string で必須 3 引数を埋め、
   default キーは strangler 値 ("bq" / "") を維持する
3. render_configmap_yaml(with_header=True) が
   `infra/manifests/search-api/configmap.example.yaml` と byte 一致

を pin する。drift しそうになると CI で即弾く。
"""

from __future__ import annotations

from pathlib import Path

from scripts.lib.config import CONFIGMAP_KEYS, generate_configmap_data, render_configmap_yaml

EXPECTED_KEYS = (
    "project_id",
    "models_bucket",
    "meili_base_url",
    "semantic_backend",
    "vertex_vector_search_index_endpoint_id",
    "vertex_vector_search_deployed_index_id",
    "feature_fetcher_backend",
    "vertex_feature_online_store_id",
    "vertex_feature_view_id",
    "vertex_feature_online_store_endpoint",
)


def test_configmap_keys_pin() -> None:
    assert tuple(CONFIGMAP_KEYS) == EXPECTED_KEYS


def test_generate_configmap_data_returns_all_keys_strings() -> None:
    data = generate_configmap_data(
        project_id="p",
        models_bucket="b",
        meili_base_url="u",
    )
    assert set(data.keys()) == set(EXPECTED_KEYS)
    assert all(isinstance(v, str) for v in data.values())


def test_strangler_defaults_preserve_phase5_behaviour() -> None:
    data = generate_configmap_data(project_id="p", models_bucket="b", meili_base_url="u")
    assert data["semantic_backend"] == "bq"
    assert data["feature_fetcher_backend"] == "bq"
    for k in (
        "vertex_vector_search_index_endpoint_id",
        "vertex_vector_search_deployed_index_id",
        "vertex_feature_online_store_id",
        "vertex_feature_view_id",
        "vertex_feature_online_store_endpoint",
    ):
        assert data[k] == ""


def test_render_committed_form_matches_example_yaml() -> None:
    """with_header=True must render byte-for-byte the committed example."""
    repo_root = Path(__file__).resolve().parents[3]
    committed = (
        repo_root / "infra" / "manifests" / "search-api" / "configmap.example.yaml"
    ).read_text(encoding="utf-8")
    data = generate_configmap_data(
        project_id="mlops-dev-a",
        models_bucket="mlops-dev-a-models",
        meili_base_url="https://meili-search-XXXXX-an.a.run.app",
    )
    assert render_configmap_yaml(data, with_header=True) == committed


def test_render_runtime_form_omits_header() -> None:
    """with_header=False is the runtime overlay form (deploy_all step 9)."""
    data = generate_configmap_data(project_id="p", models_bucket="b", meili_base_url="https://x")
    out = render_configmap_yaml(data, with_header=False)
    assert "AUTO-GENERATED" not in out
    # Each key is present once
    for k in EXPECTED_KEYS:
        assert f"  {k}:" in out
    # Empty values are double-quoted (kubectl tolerates `key: ""`, not `key:`)
    assert '  vertex_feature_view_id: ""\n' in out


def test_render_values_are_double_quoted() -> None:
    """All values use YAML double-quotes — required for empty strings."""
    data = generate_configmap_data(project_id="p", models_bucket="b", meili_base_url="u")
    out = render_configmap_yaml(data, with_header=False)
    # Every data line should match `  KEY: "VALUE"`
    for k in EXPECTED_KEYS:
        # The line begins with two spaces and ends with `"\n`.
        # Test for the simplest signature:
        assert f'  {k}: "' in out, f"{k} missing double-quote"
