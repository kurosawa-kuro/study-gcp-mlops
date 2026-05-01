"""Drift detection: ``configmap.example.yaml`` must equal the
``scripts/ci/sync_configmap.render()`` output.

The committed file is the **canonical artifact** (operators copy +
overlay it before applying). Drift between the committed file and what
``render()`` would produce from ``env/config/setting.yaml`` means
either:

1. Someone hand-edited the committed YAML without bumping setting.yaml
   (the file says "AUTO-GENERATED — do NOT edit by hand").
2. ``setting.yaml::project_id`` was bumped without rerunning
   ``make sync-configmap``.

Either way, ``make apply-manifests`` will deploy a stale ConfigMap. CI
fails fast here so the diff surfaces in the PR.
"""

from __future__ import annotations

from pathlib import Path

from scripts.ci.sync_configmap import OUTPUT, render

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_committed_configmap_matches_generator_output() -> None:
    committed = OUTPUT.read_text(encoding="utf-8")
    expected = render()
    assert committed == expected, (
        "configmap.example.yaml drifts from setting.yaml. "
        "Run `make sync-configmap` and commit the result."
    )


def test_generated_configmap_keeps_deployment_referenced_keys() -> None:
    """The generated YAML must still expose every key Deployment references.

    ``test_manifests_structure.py::test_configmap_example_covers_expected_keys``
    asserts the same against the committed file, but if a future change
    drops a generator key the manifest test would only catch it after
    ``make sync-configmap`` runs. This pins the generator output directly
    so the regression surfaces even before the committed file updates.
    """
    rendered = render()
    for required in (
        "project_id:",
        "models_bucket:",
        "meili_base_url:",
        "semantic_backend:",
        "vertex_vector_search_index_endpoint_id:",
        "vertex_vector_search_deployed_index_id:",
        "feature_fetcher_backend:",
        "vertex_feature_online_store_id:",
        "vertex_feature_view_id:",
        "vertex_feature_online_store_endpoint:",
    ):
        assert required in rendered, f"sync_configmap.render() dropped required key: {required!r}"
