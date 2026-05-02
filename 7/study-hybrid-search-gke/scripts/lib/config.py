"""ConfigMap schema — single source for sync_configmap.py and deploy_all overlay.

Phase 7 W2-5 で `scripts/setup/deploy_all.py::_run_overlay_configmap` と
`scripts/ci/sync_configmap.py::render` が同じ ConfigMap キー列を独立に
手書きしていたため、片方が更新されると drift する事故が発生した
(`feature_fetcher_backend` 系 7 キーが overlay 側のみ欠落 → search-api
Pod が `CreateContainerConfigError: couldn't find key semantic_backend` で
rollout FAILED)。

本モジュールがキー列・default 値・YAML 出力を **唯一定義**することで、
新キー追加時の更新箇所を 1 つに固定する。

I/O は行わない (subprocess / network / filesystem 不可) — 純粋データ層。
"""

from __future__ import annotations

# Group ordering preserves blank-line layout in the committed
# `infra/manifests/search-api/configmap.example.yaml`. Groups represent
# semantic clusters (env / semantic backend / feature fetcher) so future
# readers can see why a key belongs where.
_GROUPS: list[list[str]] = [
    ["project_id", "models_bucket", "meili_base_url"],
    [
        "semantic_backend",
        "vertex_vector_search_index_endpoint_id",
        "vertex_vector_search_deployed_index_id",
    ],
    [
        "feature_fetcher_backend",
        "vertex_feature_online_store_id",
        "vertex_feature_view_id",
        "vertex_feature_online_store_endpoint",
    ],
]

# Default value applied when generate_configmap_data() is not overridden.
# Committed example YAML still renders the pre-live safe values (`bq` / "").
# Runtime overlay flips the backend selectors to the canonical Vertex paths
# once Terraform outputs provide the required IDs/endpoints.
_DEFAULTS: dict[str, str] = {
    "semantic_backend": "bq",
    "vertex_vector_search_index_endpoint_id": "",
    "vertex_vector_search_deployed_index_id": "",
    "feature_fetcher_backend": "bq",
    "vertex_feature_online_store_id": "",
    "vertex_feature_view_id": "",
    "vertex_feature_online_store_endpoint": "",
}

CONFIGMAP_KEYS: list[str] = [k for group in _GROUPS for k in group]


def generate_configmap_data(
    project_id: str,
    models_bucket: str,
    meili_base_url: str,
    *,
    vertex_vector_search_index_endpoint_id: str = "",
    vertex_vector_search_deployed_index_id: str = "",
    vertex_feature_online_store_id: str = "",
    vertex_feature_view_id: str = "",
    vertex_feature_online_store_endpoint: str = "",
) -> dict[str, str]:
    """Build the search-api ConfigMap `data` mapping.

    Caller-supplied values: ``project_id``, ``models_bucket``,
    ``meili_base_url`` (these are environment-specific and resolved at
    runtime by deploy_all overlay). The backend selector keys are derived
    from the supplied runtime values:

    - both VVS IDs present -> ``semantic_backend=vertex_vector_search``
    - FOS store/view/endpoint present -> ``feature_fetcher_backend=online_store``

    Otherwise the committed-example defaults (``bq`` / empty string) remain.
    """
    data: dict[str, str] = {
        "project_id": project_id,
        "models_bucket": models_bucket,
        "meili_base_url": meili_base_url,
    }
    for k, v in _DEFAULTS.items():
        data[k] = v
    data["vertex_vector_search_index_endpoint_id"] = vertex_vector_search_index_endpoint_id
    data["vertex_vector_search_deployed_index_id"] = vertex_vector_search_deployed_index_id
    data["vertex_feature_online_store_id"] = vertex_feature_online_store_id
    data["vertex_feature_view_id"] = vertex_feature_view_id
    data["vertex_feature_online_store_endpoint"] = vertex_feature_online_store_endpoint
    if vertex_vector_search_index_endpoint_id and vertex_vector_search_deployed_index_id:
        data["semantic_backend"] = "vertex_vector_search"
    if (
        vertex_feature_online_store_id
        and vertex_feature_view_id
        and vertex_feature_online_store_endpoint
    ):
        data["feature_fetcher_backend"] = "online_store"
    return data


def render_configmap_yaml(data: dict[str, str], *, with_header: bool = False) -> str:
    """Render the ConfigMap as a kubectl-applicable YAML string.

    `with_header=True` emits the AUTO-GENERATED notice + group blank lines
    (used by `scripts/ci/sync_configmap.py` for the committed file).
    `with_header=False` emits the bare apiVersion/kind/metadata/data block
    suitable for `kubectl apply -f -` (used by deploy_all overlay).

    All values are double-quoted so empty strings remain valid YAML
    (`""`) — bare empty values would be parsed as `null` by some clients.
    """
    parts: list[str] = []
    if with_header:
        parts.append(
            "# AUTO-GENERATED from env/config/setting.yaml — do NOT edit by hand.\n"
            "# Run `make sync-configmap` to regenerate after changing setting.yaml.\n"
            "# `meili_base_url` is environment-specific (Cloud Run URL) — overlay\n"
            "# the real value before `make apply-manifests`.\n"
            "#\n"
            "# Phase 7 Wave 2 W2-5: Vertex Vector Search / Feature Online Store の\n"
            '# env vehicle を追加。default は空文字 / "bq" で暫定配線を維持し、\n'
            "# live apply / smoke 後に canonical 1 経路へ収束させる。\n"
        )
    parts.append(
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: search-api-config\n"
        "  namespace: search\n"
        "data:\n"
    )
    for i, group in enumerate(_GROUPS):
        if with_header and i > 0:
            parts.append("\n")
        for key in group:
            value = data.get(key, _DEFAULTS.get(key, ""))
            # !r → single-quoted Python repr; replace produces YAML
            # double-quoted form (matches existing committed file byte-for-byte)
            parts.append(f"  {key}: {value!r}\n".replace("'", '"'))
    return "".join(parts)
