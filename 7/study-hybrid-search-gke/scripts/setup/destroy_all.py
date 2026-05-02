"""End-to-end teardown of every Terraform-managed resource. **No interactive
prompt** — this is a learning / PDCA dev project (`mlops-dev-a`) where fast
iteration matters. Pair with `deploy-all` for a build-test-destroy loop.

Steps:

1. `seed_minimal_clean` — drop the out-of-Terraform-state table that
   `make seed-test` (`scripts/setup/seed_minimal.py`) creates. It blocks
   `feature_mart` dataset destroy with `resourceInUse` otherwise.
2. `vertex_cleanup.undeploy_all_endpoint_shells` — undeploy every
   `deployedModel` from the Terraform-managed Vertex Endpoint shells
   (server-side mutations not visible to Terraform). Any remaining
   DeployedModel blocks `terraform destroy` with HTTP 400.
3. `gcs_cleanup.wipe_all_terraform_managed_buckets` — recursively delete
   every object in the 4 force_destroy=false buckets so step 6 can
   remove the bucket resources.
4. `terraform apply -auto-approve -var=enable_deletion_protection=false
   -target=<each>` — flip `deletion_protection` to false on every
   server-side-protected resource currently in state (10 BQ tables + 1
   GKE cluster, filtered by ``filter_targets_in_state`` so already-
   destroyed resources are skipped — without that filter ``-target``
   pulls in the dependency closure and *recreates* the targets, hitting
   WIF pool soft-delete on re-run. Phase 7 Run 4 fix).
5. `kube_cleanup.delete_orphan_workloads` + `terraform destroy
   -target=module.kserve` — K8s/Helm リソースを GKE cluster より先に
   destroy (provider が cluster endpoint に依存)。state に残った場合は
   ``terraform_state.state_rm`` で fallback。
6. `terraform destroy -auto-approve` — actually tears infra down.

What this does NOT touch (preserved for the next `make deploy-all`):
- The tfstate bucket (`<PROJECT_ID>-tfstate`).
- API enablements (cost nothing when no resource exists).
- Local artifacts (`infra/tfplan`, `pipeline/data_job/dataform/workflow_settings.yaml`).

設計方針 (Phase 7 W3 リファクタ):
- 本ファイルは **orchestrator のみ**。state query / Vertex Endpoint cleanup /
  K8s finalizer cleanup / GCS bucket wipe は `scripts/infra/*` に委譲し、
  ここは順序と vars 引き渡しだけを担う。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts._common import env, run, terraform_var_args
from scripts.infra import gcs_cleanup, kube_cleanup, vertex_cleanup
from scripts.infra.terraform_state import (
    addresses_starting_with,
    filter_targets_in_state,
    state_rm,
    state_size,
)
from scripts.setup.seed_minimal_clean import main as seed_clean_main

INFRA = Path(__file__).resolve().parents[2] / "infra" / "terraform" / "environments" / "dev"

# Resource addresses that carry **server-side `deletion_protection`** —
# Terraform refuses to destroy these while the attribute is `true`. Step
# `[4/6]` runs `terraform apply -var=enable_deletion_protection=false
# -target=<each>` to flip the attribute server-side **before** the body
# destroy. Kept in sync with the corresponding Terraform module sources;
# if a new resource that has its own `deletion_protection` is added,
# append it here.
#
# 履歴:
# - Phase 6 Run 2 で BQ table `ranking_log_hourly_ctr` (T2) を追加 → 9
# - Phase 7 Run 4 で **GKE cluster** を追加 (10)
# - Phase 7 Wave 2 で online serving view `property_features_online_latest`
#   を追加 → 11
PROTECTED_TARGETS = [
    "module.data.google_bigquery_table.training_runs",
    "module.data.google_bigquery_table.search_logs",
    "module.data.google_bigquery_table.ranking_log",
    "module.data.google_bigquery_table.feedback_events",
    "module.data.google_bigquery_table.validation_results",
    "module.data.google_bigquery_table.property_features_daily",
    "module.data.google_bigquery_table.property_features_online_latest",
    "module.data.google_bigquery_table.property_embeddings",
    "module.data.google_bigquery_table.model_monitoring_alerts",
    "module.data.google_bigquery_table.ranking_log_hourly_ctr",
    "module.gke.google_container_cluster.hybrid_search",
]

# `module.kserve` 配下の K8s / Helm リソースを `terraform destroy` 本体より
# **先に** 個別 destroy するための target。`infra/terraform/environments/dev/provider.tf`
# の `kubernetes` / `helm` provider は `data.google_container_cluster.hybrid_search`
# (GKE cluster の endpoint / token) に依存しており、cluster が destroy 過程で
# 先に消えると provider が `localhost:80` に fallback して fail する。
# `module.kserve` を **module 単位で指定** することで、新規に
# `helm_release.<name>` / `kubernetes_*` を追加した時の取りこぼしを防ぐ。
KSERVE_MODULE_TARGET = "module.kserve"


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("VERTEX_LOCATION") or env("REGION")

    common_vars = [
        "-var=enable_deletion_protection=false",
        *terraform_var_args("GITHUB_REPO", "ONCALL_EMAIL"),
    ]

    print(f"==> destroy-all on project {project_id!r}")

    # 既に state が空なら destroy は何もすることがない。`-target` apply が
    # 依存ごと resource を recreate してしまう副作用 (Phase 7 Run 4 で
    # WIF pool 30 日 soft-delete に再衝突した事故) を避けるため early-return。
    state_count = state_size(INFRA)
    if state_count == 0:
        print("==> state list is empty — nothing to destroy. (前回の destroy-all で完了済)")
        print("    Re-provision with: make deploy-all")
        return 0
    print(f"==> state has {state_count} address(es) — proceeding")

    print("==> [1/6] seed-test-clean (drop out-of-TF tables that block dataset destroy)")
    seed_clean_main()

    print(f"==> [2/6] undeploy Vertex endpoint deployed_models (region={region})")
    vertex_cleanup.undeploy_all_endpoint_shells(project_id, region)

    print("==> [3/6] wipe GCS buckets (force_destroy=false blockers)")
    gcs_cleanup.wipe_all_terraform_managed_buckets(project_id)

    # state に実存する PROTECTED_TARGETS のみ flip 対象に。state にないものを
    # `-target` で渡すと Terraform は依存閉包を pull して **recreate** に走る
    # (Phase 7 Run 4 で empty-state の destroy-all 再走 → 12 resources added の
    # 事故)。filter で「flip だけ」に絞る。
    flip_targets = filter_targets_in_state(INFRA, list(PROTECTED_TARGETS))
    if flip_targets:
        print(
            f"==> [4/6] terraform apply -target=<{len(flip_targets)}/{len(PROTECTED_TARGETS)} "
            "in-state resources with deletion_protection> "
            "-var=enable_deletion_protection=false (state-flip only, no recreate)"
        )
        targets = [arg for tgt in flip_targets for arg in ("-target", tgt)]
        run(
            [
                "terraform",
                f"-chdir={INFRA}",
                "apply",
                "-auto-approve",
                *common_vars,
                *targets,
            ]
        )
    else:
        print(
            f"==> [4/6] state-flip skipped — "
            f"PROTECTED_TARGETS ({len(PROTECTED_TARGETS)}) はいずれも state 不在"
        )

    print(
        "==> [5/6] terraform destroy -target=module.kserve "
        "(K8s/Helm を GKE cluster より先に削除 — provider が cluster endpoint に依存するため)"
    )
    # operator destroy より先に CR を消して finalizer deadlock を避ける。
    kube_cleanup.delete_orphan_workloads()
    proc = subprocess.run(
        [
            "terraform",
            f"-chdir={INFRA}",
            "destroy",
            "-auto-approve",
            *common_vars,
            f"-target={KSERVE_MODULE_TARGET}",
        ],
        check=False,
    )
    # exit code が 0 でも、cluster unreachable で何も消せなかった ↔ state には
    # 残ってる、というケースが起きうる (Phase 7 Run 4 で観測)。後方確認として
    # `terraform state list` で残存を直接見る。
    remaining = addresses_starting_with(INFRA, f"{KSERVE_MODULE_TARGET}.")
    if proc.returncode != 0 or remaining:
        reason = (
            "exit code 非 0"
            if proc.returncode != 0
            else f"exit 0 だが state に {len(remaining)} 件残存"
        )
        print(
            f"    targeted destroy で K8s/Helm を片付けきれず ({reason}) — "
            "GKE cluster 既消滅の可能性。state rm で fallback 後、本体 destroy へ進む。"
        )
        if remaining:
            print(f"    module.kserve in state: {len(remaining)} address(es) → state rm")
            for addr in remaining:
                print(f"      {addr}")
            state_rm(INFRA, KSERVE_MODULE_TARGET)
        else:
            print("    module.kserve in state: empty (nothing to rm)")

    print("==> [6/6] terraform destroy -auto-approve (本体)")
    run(
        [
            "terraform",
            f"-chdir={INFRA}",
            "destroy",
            "-auto-approve",
            *common_vars,
        ]
    )

    print()
    print("==> destroy-all complete.")
    print("    tfstate bucket preserved. Re-provision with: make deploy-all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
