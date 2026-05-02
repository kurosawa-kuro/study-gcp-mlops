"""Phase 7 workflow contract — `make destroy-all` teardown + reproducibility.

Pin the destroy ordering, the Vertex Endpoint deployed-model undeploy, the
Vector Search deployed-index undeploy guard (PDCA reproducibility),
BigQuery `deletion_protection` flip, GCS bucket `force_destroy` wipe, and
the WIF pool soft-delete recovery.
"""

from __future__ import annotations

from scripts.setup import destroy_all
from tests.integration.workflow.conftest import read_repo_file as _read


def test_destroy_all_keeps_pdca_reproducibility_guards() -> None:
    assert "module.gke.google_container_cluster.hybrid_search" in destroy_all.PROTECTED_TARGETS
    assert "module.data.google_bigquery_table.property_features_daily" in (
        destroy_all.PROTECTED_TARGETS
    )
    assert destroy_all.KSERVE_MODULE_TARGET == "module.kserve"

    source = _read("scripts/setup/destroy_all.py")
    assert "state list is empty — nothing to destroy" in source
    assert "seed-test-clean" in source
    assert "undeploy Vertex endpoint deployed_models" in source
    assert "terraform destroy -target=module.kserve" in source
    assert "terraform destroy -auto-approve (本体)" in source


def test_destroy_all_destroy_apply_symmetry() -> None:
    """**destroy-all ↔ deploy-all 対称性**: deploy-all が立てる主要 module は
    destroy-all で `terraform destroy -auto-approve` の連鎖で消える契約。

    KServe Helm provider race を回避する `KSERVE_MODULE_TARGET` 先行 destroy が
    維持されていることを pin。
    """
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    deploy_all_py = _read("scripts/setup/deploy_all.py")

    assert 'KSERVE_MODULE_TARGET = "module.kserve"' in destroy_all_py
    assert "terraform destroy -target=module.kserve" in destroy_all_py

    for required_module in (
        "module.iam",
        "module.data",
        "module.vector_search",
        "module.vertex",
        "module.gke",
        "module.composer",
    ):
        assert required_module in deploy_all_py, (
            f"deploy-all stage1 targets must include {required_module}"
        )


def test_destroy_all_undeploys_vertex_endpoint_models_before_destroy() -> None:
    """Vertex AI Endpoint の `deployedModels` が undeploy 済になってから
    `terraform destroy` する契約。

    Endpoint が deployed_model を持つ状態で destroy すると HTTP 400
    `Endpoint has deployed or being-deployed DeployedModel(s)`、手動 cleanup
    で 5-15 min ロス。"""
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    assert "vertex_cleanup.undeploy_all_endpoint_shells" in destroy_all_py


def test_destroy_all_proactively_undeploys_stale_vvs_indexes() -> None:
    """**PDCA reproducibility 契約** (2026-05-02 追加): `destroy-all` は
    Vector Search の deployed index を能動的に undeploy する。

    過去事故: 前 PDCA cycle が deployed index を残したまま終わると、次の
    `make deploy-all` step 6 で 15 min wait timeout で fail。`deploy-all` 側
    `wait_for_deployed_index_absent` は wait しかしないため、destroy 側に
    proactive undeploy を入れる責任がある。"""
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    vertex_cleanup_py = _read("scripts/infra/vertex_cleanup.py")

    assert "def undeploy_all_vvs_deployed_indexes(" in vertex_cleanup_py
    assert '"undeploy-index"' in vertex_cleanup_py, (
        "must invoke 'gcloud ai index-endpoints undeploy-index' (not just describe / wait)"
    )
    assert "vertex_cleanup.undeploy_all_vvs_deployed_indexes" in destroy_all_py


def test_destroy_all_flips_bq_deletion_protection_before_destroy() -> None:
    """BigQuery table の `deletion_protection=true` を destroy 前に **state-flip**
    する契約 (Terraform default で destroy 拒否される)。"""
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    data_tf = _read("infra/terraform/modules/data/main.tf")

    assert "PROTECTED_TARGETS" in destroy_all_py
    assert "enable_deletion_protection=false" in destroy_all_py

    declared_tables = __import__("re").findall(
        r'resource "google_bigquery_table" "(\w+)"',
        data_tf,
    )
    for table_resource in declared_tables:
        assert table_resource in destroy_all_py or "deletion_protection = false" in data_tf, (
            f"google_bigquery_table.{table_resource} should appear in destroy_all.py "
            "PROTECTED_TARGETS (BQ default deletion_protection=true)"
        )


def test_destroy_all_force_destroys_blocking_gcs_buckets() -> None:
    """`force_destroy=false` な GCS bucket が中身を持つと destroy が止まる。
    `gcloud storage rm --recursive` で wipe してから destroy する契約。"""
    destroy_all_py = _read("scripts/setup/destroy_all.py")
    assert "gcs_cleanup" in destroy_all_py
    assert "wipe_all_terraform_managed_buckets" in destroy_all_py


def test_recover_wif_handles_soft_delete_undelete() -> None:
    """destroy → 即 deploy で WIF pool が soft-delete (30 日保持) のため
    409 conflict になるのを undelete で recover する契約。

    自動化なしだと 30 日間 WIF が使えず destroy-all 後の deploy 完全 block。"""
    deploy_all_py = _read("scripts/setup/deploy_all.py")
    recover_wif_py = _read("scripts/setup/recover_wif.py")

    assert "recover_wif" in deploy_all_py, "deploy-all must call recover_wif before terraform apply"
    assert "undelete" in recover_wif_py.lower(), (
        "recover_wif.py must handle WIF pool undelete (30-day soft-delete window)"
    )


def test_destroy_all_persists_vvs_index_and_endpoint() -> None:
    """**VVS 永続化契約** (2026-05-03 追加、`docs/tasks/Vertex Vector Search時間短縮.md`):
    Vertex Vector Search の Index と Index Endpoint は **無料で残せる** (replica 0
    の Endpoint と未 deploy の Index は課金されない)。Index build に 5-15 min、
    Endpoint 作成に数分 + DNS propagation がかかるため、PDCA cycle ごとに作り
    直すと deploy-all 27 min → 10-15 min の短縮効果が出ない。

    本契約は以下を pin する:
    1. `module.vector_search` の Index と Endpoint が `lifecycle { prevent_destroy = true }`
    2. `destroy_all.py` の `PERSISTENT_VVS_RESOURCES` に Index / Endpoint アドレス
    3. `destroy_all.py` が state_list 全件から永続化アドレスを除いた集合を `-target` 指定して destroy
    """
    main_tf = _read("infra/terraform/modules/vector_search/main.tf")
    destroy_all_py = _read("scripts/setup/destroy_all.py")

    # main.tf — Index / Endpoint に prevent_destroy
    import re as _re

    index_block = _re.search(
        r'resource "google_vertex_ai_index" "property_embeddings" \{.*?\n\}',
        main_tf,
        flags=_re.DOTALL,
    )
    endpoint_block = _re.search(
        r'resource "google_vertex_ai_index_endpoint" "property_embeddings" \{.*?\n\}',
        main_tf,
        flags=_re.DOTALL,
    )
    deployed_block = _re.search(
        r'resource "google_vertex_ai_index_endpoint_deployed_index" "property_embeddings" \{.*?\n\}',
        main_tf,
        flags=_re.DOTALL,
    )
    assert index_block is not None and endpoint_block is not None
    assert "prevent_destroy = true" in index_block.group(0), (
        "google_vertex_ai_index.property_embeddings must declare lifecycle.prevent_destroy=true"
    )
    assert "prevent_destroy = true" in endpoint_block.group(0), (
        "google_vertex_ai_index_endpoint.property_embeddings must declare lifecycle.prevent_destroy=true"
    )
    # deployed_index は永続化対象外 (これが課金 resource、PDCA 毎に destroy する)
    if deployed_block is not None:
        assert "prevent_destroy = true" not in deployed_block.group(0), (
            "google_vertex_ai_index_endpoint_deployed_index must NOT have prevent_destroy "
            "(this is the billed replica resource, must be destroyed each PDCA cycle)"
        )

    # destroy_all.py の persistent list
    assert "PERSISTENT_VVS_RESOURCES" in destroy_all_py
    assert (
        '"module.vector_search.google_vertex_ai_index.property_embeddings"'
        in destroy_all_py
    )
    assert (
        '"module.vector_search.google_vertex_ai_index_endpoint.property_embeddings"'
        in destroy_all_py
    )
    # destroy 時に state_list で全 addr を取得 → persistent を除外して -target 指定
    assert "state_list(INFRA)" in destroy_all_py
    assert "persistent_prefixes" in destroy_all_py


def test_no_vertex_pipeline_job_schedule_resource_in_terraform() -> None:
    """カニバリ NG: Vertex `PipelineJobSchedule` は Phase 7 で完全撤去
    (docs/01 §3.6)。Composer DAG schedule との二重起動を防ぐ。"""
    from tests.integration.workflow.conftest import REPO_ROOT

    tf_dir = REPO_ROOT / "infra" / "terraform"
    forbidden_patterns = ("google_vertex_ai_pipeline_job_schedule", "PipelineJobSchedule")
    for tf_file in tf_dir.rglob("*.tf"):
        text = tf_file.read_text(encoding="utf-8")
        for forbidden in forbidden_patterns:
            assert forbidden not in text, (
                f"{tf_file.relative_to(REPO_ROOT)} contains forbidden {forbidden!r} "
                "(Phase 7 W2-4 で撤去済、§3.6 カニバリ NG で再導入禁止)"
            )
