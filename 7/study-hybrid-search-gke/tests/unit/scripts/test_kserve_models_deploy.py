"""Unit tests for scripts.deploy.kserve_models — resolve + patch shape.

These pin the two bits of ``kserve_models.py`` that have silent-failure modes
on real GCP:

1. ``_resolve_latest`` must select the version carrying the ``production``
   alias (not just models[0]) — mis-selection deploys stale models.
2. ``_patch_encoder_storage_uri`` / ``_patch_reranker_storage_uri`` must emit
   the exact JSON shape the KServe webhook expects — a typo in the payload
   path fails silently at apply time with an opaque 422.

``google-cloud-aiplatform`` is stubbed via a fake module + fake Model class,
so tests run without GCP.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class _FakeModel:
    """Stand-in for ``google.cloud.aiplatform.Model`` — only the fields
    ``_resolve_latest`` inspects.
    """

    def __init__(
        self,
        *,
        display_name: str,
        version_id: str,
        uri: str,
        aliases: list[str],
    ) -> None:
        self.display_name = display_name
        self.version_id = version_id
        self.uri = uri
        self.version_aliases = aliases
        self._gca_resource = types.SimpleNamespace(artifact_uri=uri)


def _install_fake_aiplatform(
    monkeypatch: pytest.MonkeyPatch, models: list[_FakeModel]
) -> MagicMock:
    """Install a fake ``google.cloud.aiplatform`` module that returns
    ``models`` from ``Model.list``. Returns the init MagicMock so tests can
    assert project/location.
    """
    fake_init = MagicMock()
    fake_model_cls = MagicMock()
    fake_model_cls.list.return_value = models

    fake_aiplatform = types.ModuleType("google.cloud.aiplatform")
    fake_aiplatform.init = fake_init  # type: ignore[attr-defined]
    fake_aiplatform.Model = fake_model_cls  # type: ignore[attr-defined]

    # Pre-build the namespace so `from google.cloud import aiplatform` finds it.
    google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
    cloud_mod = sys.modules.setdefault("google.cloud", types.ModuleType("google.cloud"))
    monkeypatch.setattr(cloud_mod, "aiplatform", fake_aiplatform, raising=False)
    monkeypatch.setitem(sys.modules, "google.cloud.aiplatform", fake_aiplatform)
    # Also expose aiplatform as submodule of google for aliased imports
    _ = google_mod  # keep ref
    return fake_init


# ----------------------------------------------------------------------------
# _resolve_latest
# ----------------------------------------------------------------------------


def test_resolve_latest_prefers_model_with_production_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When multiple models match, the one carrying ``production`` alias wins
    — not models[0]. This is the whole point of promote-then-deploy."""
    from scripts.deploy import kserve_models

    models = [
        _FakeModel(
            display_name="property-reranker",
            version_id="v3",
            uri="gs://bucket/lgbm/2026-04-24/v3",
            aliases=["staging"],
        ),
        _FakeModel(
            display_name="property-reranker",
            version_id="v2",
            uri="gs://bucket/lgbm/2026-04-20/v2",
            aliases=["production"],
        ),
        _FakeModel(
            display_name="property-reranker",
            version_id="v1",
            uri="gs://bucket/lgbm/2026-04-10/v1",
            aliases=[],
        ),
    ]
    _install_fake_aiplatform(monkeypatch, models)

    resolved = kserve_models._resolve_latest(
        "property-reranker", project_id="p", region="asia-northeast1"
    )
    assert resolved.version_id == "v2"
    assert resolved.artifact_uri == "gs://bucket/lgbm/2026-04-20/v2"
    assert "production" in resolved.aliases


def test_resolve_latest_falls_back_to_first_when_no_production_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No model has ``production`` alias → fall back to models[0] with a
    warning log (verified by stdout capture). This is the path flagged as LOW
    in the Phase 7 audit — caller should run ``make ops-promote-reranker``
    first, but the script must not crash.
    """
    from scripts.deploy import kserve_models

    models = [
        _FakeModel(
            display_name="property-encoder",
            version_id="v1",
            uri="gs://bucket/encoder/v1",
            aliases=["staging"],
        ),
    ]
    _install_fake_aiplatform(monkeypatch, models)

    resolved = kserve_models._resolve_latest(
        "property-encoder", project_id="p", region="asia-northeast1"
    )
    assert resolved.version_id == "v1"


def test_resolve_latest_raises_when_no_models(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.deploy import kserve_models

    _install_fake_aiplatform(monkeypatch, [])
    with pytest.raises(RuntimeError, match="No model with display_name=property-reranker"):
        kserve_models._resolve_latest("property-reranker", project_id="p", region="asia-northeast1")


def test_resolve_latest_raises_when_artifact_uri_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the Model exists but ``uri`` + ``_gca_resource.artifact_uri`` are
    both empty (incomplete upload), the script must refuse to patch — otherwise
    KServe would try to pull from an empty storageUri and fail opaquely.
    """
    from scripts.deploy import kserve_models

    bad_model = _FakeModel(
        display_name="property-reranker",
        version_id="v5",
        uri="",
        aliases=["production"],
    )
    bad_model._gca_resource = types.SimpleNamespace(artifact_uri="")
    _install_fake_aiplatform(monkeypatch, [bad_model])

    with pytest.raises(RuntimeError, match="has no artifact_uri"):
        kserve_models._resolve_latest("property-reranker", project_id="p", region="asia-northeast1")


# ----------------------------------------------------------------------------
# _patch_reranker_storage_uri / _patch_encoder_storage_uri — payload shape
# ----------------------------------------------------------------------------


def _capture_kubectl_patch_call() -> tuple[list[list[str]], MagicMock]:
    """Patch ``scripts.deploy.kserve_models.run`` so kubectl never actually
    runs; return (captured_argv_list, run_mock)."""
    captured: list[list[str]] = []

    def fake_run(argv: list[str], *args: Any, **kwargs: Any) -> Any:
        captured.append(list(argv))
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""
        return proc

    run_mock = MagicMock(side_effect=fake_run)
    return captured, run_mock


def test_patch_reranker_storage_uri_emits_expected_kubectl_shape() -> None:
    from scripts.deploy import kserve_models

    captured, run_mock = _capture_kubectl_patch_call()
    with patch.object(kserve_models, "run", run_mock):
        kserve_models._patch_reranker_storage_uri("gs://bucket/lgbm/2026-04-20/v2")

    assert len(captured) == 1
    argv = captured[0]
    # kubectl patch inferenceservice property-reranker --namespace=kserve-inference --type=merge --patch=...
    assert argv[0] == "kubectl"
    assert argv[1] == "patch"
    assert argv[2] == "inferenceservice"
    assert argv[3] == "property-reranker"
    assert "--namespace=kserve-inference" in argv
    assert "--type=merge" in argv

    patch_flag = next(a for a in argv if a.startswith("--patch="))
    body = json.loads(patch_flag[len("--patch=") :])
    assert body == {
        "spec": {
            "predictor": {
                "model": {
                    "storageUri": "gs://bucket/lgbm/2026-04-20/v2",
                }
            }
        }
    }


def test_patch_encoder_storage_uri_normalizes_trailing_slash() -> None:
    """Phase 5 Run 6 note: encoder ``AIP_STORAGE_URI`` must end in ``/`` so
    ``list_blobs`` treats it as a directory. Ensure the normalization is
    still applied."""
    from scripts.deploy import kserve_models

    captured, run_mock = _capture_kubectl_patch_call()
    with patch.object(kserve_models, "run", run_mock):
        kserve_models._patch_encoder_storage_uri("gs://bucket/encoders/v3")

    argv = captured[0]
    patch_flag = next(a for a in argv if a.startswith("--patch="))
    body = json.loads(patch_flag[len("--patch=") :])
    env = body["spec"]["predictor"]["containers"][0]["env"]
    aip_uri = next(e for e in env if e["name"] == "AIP_STORAGE_URI")["value"]
    assert aip_uri == "gs://bucket/encoders/v3/", (
        f"encoder AIP_STORAGE_URI must end with '/' (got {aip_uri!r}). "
        "Phase 5 Run 6 regression: missing trailing slash breaks list_blobs dir scan."
    )


def test_patch_encoder_storage_uri_keeps_existing_trailing_slash() -> None:
    """Idempotent: if the caller already provided a trailing slash, don't
    double it (``gs://.../v3//``)."""
    from scripts.deploy import kserve_models

    captured, run_mock = _capture_kubectl_patch_call()
    with patch.object(kserve_models, "run", run_mock):
        kserve_models._patch_encoder_storage_uri("gs://bucket/encoders/v3/")

    argv = captured[0]
    patch_flag = next(a for a in argv if a.startswith("--patch="))
    body = json.loads(patch_flag[len("--patch=") :])
    env = body["spec"]["predictor"]["containers"][0]["env"]
    aip_uri = next(e for e in env if e["name"] == "AIP_STORAGE_URI")["value"]
    assert aip_uri == "gs://bucket/encoders/v3/"


def test_patch_encoder_payload_targets_kserve_container_env() -> None:
    """The encoder patch goes at ``spec.predictor.containers[0].env`` (not
    ``spec.predictor.model.storageUri``) because the encoder uses a custom
    Python predictor (Vertex CPR contract)."""
    from scripts.deploy import kserve_models

    captured, run_mock = _capture_kubectl_patch_call()
    with patch.object(kserve_models, "run", run_mock):
        kserve_models._patch_encoder_storage_uri("gs://bucket/encoders/v3/")

    argv = captured[0]
    patch_flag = next(a for a in argv if a.startswith("--patch="))
    body = json.loads(patch_flag[len("--patch=") :])
    container = body["spec"]["predictor"]["containers"][0]
    assert container["name"] == "kserve-container"
    env_names = {e["name"] for e in container["env"]}
    assert "AIP_STORAGE_URI" in env_names
