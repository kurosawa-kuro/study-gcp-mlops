"""Structural invariants for the Phase 7 K8s manifests (``infra/manifests/``).

The manifests are Terraform-external (applied via ``kubectl apply -k``), so
they escape ``make tf-validate``. These tests keep the most error-prone bits
(resource limits, HPA bounds, NetworkPolicy boundary, KServe InferenceService
contract, ConfigMap env keys) from silently drifting.

Loads each YAML via ``yaml.safe_load_all`` — no ``kubectl`` / ``kustomize``
CLI dependency, works offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFESTS_DIR = REPO_ROOT / "infra" / "manifests"
SEARCH_API_DIR = MANIFESTS_DIR / "search-api"
KSERVE_DIR = MANIFESTS_DIR / "kserve"


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fp:
        docs = [doc for doc in yaml.safe_load_all(fp) if doc is not None]
    assert len(docs) == 1, f"{path.name} must carry exactly one resource doc, got {len(docs)}"
    return docs[0]


# ----------------------------------------------------------------------------
# Kustomization — ensures kubectl apply -k finds everything
# ----------------------------------------------------------------------------


def test_kustomization_lists_every_yaml_under_manifests() -> None:
    kust = _load(MANIFESTS_DIR / "kustomization.yaml")
    listed = {entry for entry in kust.get("resources", [])}
    # Every non-kustomization yaml under infra/manifests/**/*.yaml must be listed
    on_disk: set[str] = set()
    for subdir in (SEARCH_API_DIR, KSERVE_DIR):
        for yml in sorted(subdir.glob("*.yaml")):
            on_disk.add(f"{subdir.name}/{yml.name}")
    missing = on_disk - listed
    stale = listed - on_disk
    assert not missing, f"kustomization.yaml missing entries: {sorted(missing)}"
    assert not stale, f"kustomization.yaml references non-existent files: {sorted(stale)}"


# ----------------------------------------------------------------------------
# search-api Deployment — resource limits non-negotiable
# ----------------------------------------------------------------------------


def test_search_api_deployment_resource_limits_match_nonnegotiable() -> None:
    """CLAUDE.md non-negotiable: requests=500m/1Gi, limits=2/2Gi. Deviating
    here breaks the documented cost envelope — flag any drift explicitly.
    """
    dep = _load(SEARCH_API_DIR / "deployment.yaml")
    assert dep["kind"] == "Deployment"
    assert dep["metadata"]["namespace"] == "search"
    assert dep["metadata"]["name"] == "search-api"

    containers = dep["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1, "search-api Pod must run exactly one container"
    resources = containers[0]["resources"]
    assert resources["requests"] == {"cpu": "500m", "memory": "1Gi"}, (
        "requests must be 500m CPU / 1Gi memory (CLAUDE.md non-negotiable)."
    )
    assert resources["limits"] == {"cpu": "2", "memory": "2Gi"}, (
        "limits must be 2 CPU / 2Gi memory (CLAUDE.md non-negotiable)."
    )


def test_search_api_deployment_exposes_kserve_env_vars() -> None:
    """The Deployment's baked-in env must wire the Phase 7 KServe URLs. If
    someone removes the env entry without adding a ConfigMap fallback, the
    KServeEncoder/Reranker will silently disable themselves at composition
    root (empty-string gate) and /search will 503 in production.
    """
    dep = _load(SEARCH_API_DIR / "deployment.yaml")
    env = dep["spec"]["template"]["spec"]["containers"][0].get("env", [])
    env_keys = {e["name"] for e in env}

    required_keys = {
        "KSERVE_ENCODER_URL",
        "KSERVE_RERANKER_URL",
        "ENABLE_SEARCH",
        "ENABLE_RERANK",
        "RANKING_LOG_TOPIC",
        "FEEDBACK_TOPIC",
        "RETRAIN_TOPIC",
    }
    missing = required_keys - env_keys
    assert not missing, f"deployment.yaml missing env keys: {sorted(missing)}"

    # KServe URLs must point at cluster-local DNS (not localhost / placeholder)
    by_name = {e["name"]: e.get("value", "") for e in env}
    assert "kserve-inference.svc.cluster.local" in by_name["KSERVE_ENCODER_URL"], (
        f"KSERVE_ENCODER_URL must be cluster-local DNS, got {by_name['KSERVE_ENCODER_URL']!r}"
    )
    assert "kserve-inference.svc.cluster.local" in by_name["KSERVE_RERANKER_URL"], (
        f"KSERVE_RERANKER_URL must be cluster-local DNS, got {by_name['KSERVE_RERANKER_URL']!r}"
    )


def test_search_api_deployment_readiness_probe_hits_livez_not_healthz() -> None:
    """Knative/GFE reserved /healthz as HTML 404 in Phase 5; the app moved
    liveness to /livez. Readiness probe must target /livez to avoid
    regressing the GFE-reserved path in the GKE rollout.
    """
    dep = _load(SEARCH_API_DIR / "deployment.yaml")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    readiness = container["readinessProbe"]["httpGet"]["path"]
    liveness = container["livenessProbe"]["httpGet"]["path"]
    assert readiness == "/livez", f"readinessProbe must hit /livez (got {readiness!r})"
    assert liveness == "/livez", f"livenessProbe must hit /livez (got {liveness!r})"


# ----------------------------------------------------------------------------
# HPA — min/max + CPU/Memory thresholds
# ----------------------------------------------------------------------------


def test_search_api_hpa_bounds_and_thresholds() -> None:
    """CLAUDE.md: minReplicas=1 maxReplicas=10 HPA CPU 70% / Mem 80%."""
    hpa = _load(SEARCH_API_DIR / "hpa.yaml")
    assert hpa["kind"] == "HorizontalPodAutoscaler"
    assert hpa["spec"]["minReplicas"] == 1
    assert hpa["spec"]["maxReplicas"] == 10
    metrics_by_resource = {
        m["resource"]["name"]: m["resource"]["target"]["averageUtilization"]
        for m in hpa["spec"]["metrics"]
        if m.get("type") == "Resource"
    }
    assert metrics_by_resource.get("cpu") == 70, "HPA CPU threshold must be 70%"
    assert metrics_by_resource.get("memory") == 80, "HPA Memory threshold must be 80%"


# ----------------------------------------------------------------------------
# NetworkPolicy — search ns egress only to kserve-inference + GCP + DNS
# ----------------------------------------------------------------------------


def test_search_api_networkpolicy_allows_egress_to_kserve_inference() -> None:
    np = _load(SEARCH_API_DIR / "networkpolicy.yaml")
    assert np["kind"] == "NetworkPolicy"
    assert np["metadata"]["namespace"] == "search"
    assert "Egress" in np["spec"]["policyTypes"]

    # At least one egress rule must target kserve-inference namespace
    found = False
    for rule in np["spec"]["egress"]:
        for peer in rule.get("to", []):
            ns_sel = peer.get("namespaceSelector", {}).get("matchLabels", {})
            if ns_sel.get("kubernetes.io/metadata.name") == "kserve-inference":
                found = True
                break
    assert found, (
        "search NetworkPolicy must allow egress to kserve-inference namespace. "
        "Otherwise KServeEncoder/Reranker HTTP calls will be blocked cluster-locally."
    )


# ----------------------------------------------------------------------------
# KServe InferenceService — encoder + reranker contract
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["property-encoder", "property-reranker"])
def test_kserve_inferenceservice_has_correct_shape(name: str) -> None:
    isvc = _load(KSERVE_DIR / f"{name.split('-')[1]}.yaml")
    assert isvc["apiVersion"].startswith("serving.kserve.io/")
    assert isvc["kind"] == "InferenceService"
    assert isvc["metadata"]["name"] == name
    assert isvc["metadata"]["namespace"] == "kserve-inference"

    predictor = isvc["spec"]["predictor"]
    # Minimum replicas must be >= 1 to avoid KServe cold-start latency (docs).
    assert predictor.get("minReplicas", 0) >= 1, (
        f"{name}: minReplicas must be >= 1 to avoid KServe cold-start latency. "
        "docs/02_移行ロードマップ.md §3.5 forbids minReplicas=0 for learning-repo cost."
    )


def test_kserve_reranker_uses_lightgbm_model_format() -> None:
    """The reranker must declare modelFormat=lightgbm so MLServer's built-in
    LightGBM runtime picks up the model.txt artifact. Changing this silently
    (to e.g. ``triton`` / ``sklearn``) would break model loading."""
    isvc = _load(KSERVE_DIR / "reranker.yaml")
    model = isvc["spec"]["predictor"]["model"]
    assert model["modelFormat"]["name"] == "lightgbm"
    assert "storageUri" in model


def test_kserve_networkpolicy_restricts_ingress_to_search_namespace() -> None:
    np = _load(KSERVE_DIR / "networkpolicy.yaml")
    assert np["kind"] == "NetworkPolicy"
    assert np["metadata"]["namespace"] == "kserve-inference"
    # Must restrict ingress to search namespace (not allow-all)
    ingress_rules = np["spec"].get("ingress", [])
    assert ingress_rules, "kserve-inference NetworkPolicy must declare explicit ingress rules"
    # At least one ingress must reference namespace search
    found = False
    for rule in ingress_rules:
        for peer in rule.get("from", []):
            ns_sel = peer.get("namespaceSelector", {}).get("matchLabels", {})
            if ns_sel.get("kubernetes.io/metadata.name") == "search":
                found = True
                break
    assert found, (
        "kserve-inference ingress must whitelist the `search` namespace. "
        "Without this, search-api → KServe calls are blocked by default-deny."
    )


# ----------------------------------------------------------------------------
# ConfigMap example — schema alignment with ApiSettings
# ----------------------------------------------------------------------------


def test_configmap_example_covers_expected_keys() -> None:
    """configmap.example.yaml documents the keys the Deployment references
    via ``valueFrom.configMapKeyRef``. Drift between the two produces silent
    ``env CONFIG_NOT_FOUND`` at Pod startup, which ``kubectl describe``
    flags but is easy to miss on first deploy.
    """
    dep = _load(SEARCH_API_DIR / "deployment.yaml")
    referenced: set[str] = set()
    for env in dep["spec"]["template"]["spec"]["containers"][0].get("env", []):
        ref = env.get("valueFrom", {}).get("configMapKeyRef")
        if ref and ref.get("name") == "search-api-config":
            referenced.add(ref["key"])

    cm = _load(SEARCH_API_DIR / "configmap.example.yaml")
    assert cm["kind"] == "ConfigMap"
    assert cm["metadata"]["name"] == "search-api-config"
    provided = set(cm.get("data", {}).keys())

    missing = referenced - provided
    assert not missing, (
        f"deployment.yaml references ConfigMap keys that configmap.example.yaml does "
        f"not document: {sorted(missing)}. Either add them to the example or wire the "
        "env to a literal value in deployment.yaml."
    )
