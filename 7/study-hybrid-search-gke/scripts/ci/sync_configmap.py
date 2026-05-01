"""Generate infra/manifests/search-api/configmap.example.yaml from setting.yaml.

Why a generator instead of hand-editing:
- ``project_id`` must match ``env/config/setting.yaml`` (single source of
  truth) so a one-line edit there propagates to the manifest.
- ``models_bucket`` follows the convention ``<project_id>-models`` set in
  ``ml/common/config/base.py::BaseAppSettings.gcs_models_bucket`` default.
  Hardcoding it in the manifest is a drift trap.
- ``meili_base_url`` is environment-specific (Cloud Run URL set per
  deploy) so we keep a placeholder constant. The expectation is documented
  inline so operators know what to overlay before ``make apply-manifests``.

Pair with ``tests/integration/infra/test_configmap_drift.py`` which fails
CI if the generator output drifts from the committed file.
"""

from __future__ import annotations

from pathlib import Path

from scripts._common import DEFAULTS

OUTPUT = (
    Path(__file__).resolve().parent.parent.parent
    / "infra"
    / "manifests"
    / "search-api"
    / "configmap.example.yaml"
)

# Placeholder kept in the example file. Operators overlay the real Cloud
# Run URL via env-specific kustomization or `kubectl create configmap
# --from-literal` before applying.
MEILI_BASE_URL_PLACEHOLDER = "https://meili-search-XXXXX-an.a.run.app"


def render() -> str:
    project_id = DEFAULTS.get("PROJECT_ID")
    if not project_id:
        raise SystemExit("env/config/setting.yaml is missing required key: project_id")
    models_bucket = f"{project_id}-models"
    return (
        "# AUTO-GENERATED from env/config/setting.yaml — do NOT edit by hand.\n"
        "# Run `make sync-configmap` to regenerate after changing setting.yaml.\n"
        "# `meili_base_url` is environment-specific (Cloud Run URL) — overlay\n"
        "# the real value before `make apply-manifests`.\n"
        "#\n"
        "# Phase 7 Wave 2 W2-5: Vertex Vector Search / Feature Online Store の\n"
        '# env vehicle を追加。default は空文字 / "bq" で暫定配線を維持し、\n'
        "# live apply / smoke 後に canonical 1 経路へ収束させる。\n"
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: search-api-config\n"
        "  namespace: search\n"
        "data:\n"
        f"  project_id: {project_id!r}\n".replace("'", '"')
        + f"  models_bucket: {models_bucket!r}\n".replace("'", '"')
        + f"  meili_base_url: {MEILI_BASE_URL_PLACEHOLDER!r}\n".replace("'", '"')
        + "\n"
        + '  semantic_backend: "bq"\n'
        + '  vertex_vector_search_index_endpoint_id: ""\n'
        + '  vertex_vector_search_deployed_index_id: ""\n'
        + "\n"
        + '  feature_fetcher_backend: "bq"\n'
        + '  vertex_feature_online_store_id: ""\n'
        + '  vertex_feature_view_id: ""\n'
        + '  vertex_feature_online_store_endpoint: ""\n'
    )


def main() -> int:
    content = render()
    rel = OUTPUT.relative_to(OUTPUT.parents[3])
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") == content:
        print(f"==> {rel} already up to date")
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"==> wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
