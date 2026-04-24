"""End-to-end teardown of every Terraform-managed resource (Phase 6). **No
interactive prompt** — this is a learning / PDCA dev project (`mlops-dev-a`)
where fast iteration matters. Pair with `deploy-all` for a build-test-destroy
loop.

Phase 6 ordering (distinct from Phase 5 because serving layer moved to
GKE + KServe):

1. `seed-test-clean` — drop `feature_mart.properties_cleaned` + friends that
   `make seed-test` creates out-of-Terraform-state (blocks dataset destroy).
2. **`kubectl delete -k infra/manifests/`** — tear down search-api Deployment +
   InferenceService + NetworkPolicy + Gateway + BackendConfig so the GKE side
   doesn't block `terraform destroy module.gke`. `--ignore-not-found` makes
   this benign when the manifests were never applied.
3. **`kubectl delete namespace search kserve-inference cert-manager`** — finalizers
   on KServe CRDs can leave stuck namespaces. Force-delete after manifest drain.
4. `gcloud storage rm --recursive` on the 4 Terraform-managed buckets
   (models / artifacts / pipeline-root / meili-data). All have
   `force_destroy = false` hardcoded, so `terraform destroy` fails with
   "containing objects without `force_destroy` set to true" when any hold
   objects from a prior run. Wiping is pragmatic: destroy-all is a learn/PDCA
   target where losing model artifacts + pipeline roots is intended.
5. `terraform apply -target=<each protected BQ table>` — flip every BQ table's
   `deletion_protection` to false. `-target` is **load-bearing**: a bare apply
   would also try to (re)create any drifted resource.
6. `terraform destroy -auto-approve` — actually tears infra down.

過去実害の再発防止:

* Phase 5 Run 8 v1: Vertex Endpoint の deployedModels が残って HTTP 400 で詰まる
  → Phase 6 は Vertex Endpoint を作らないため step 削除 (docs/02_移行ロードマップ.md §11.7)
* Phase 5 Run 8 v2: 4 GCS buckets に object 残存で `force_destroy=false` エラー
  → Phase 6 でも同じなので step 4 を継承
* Phase 5 Run 8 v2: `model_monitoring_alerts` table が protected リストから漏れ
  → Phase 6 は Vertex Monitoring v2 縮退でこの table を作らないが、念のため
    `PROTECTED_TABLE_TARGETS` には含めて destroy の冪等性を担保 (table 不在時は
    `-target` が no-op で benign)
* Phase 6 新規: GKE Deployment / KServe InferenceService が `terraform destroy
  module.gke` を HTTP 400 で詰まらせるリスク → step 2-3 で先に K8s 側を drain

What this does NOT touch (preserved for the next `make deploy-all`):

- The tfstate bucket (`<PROJECT_ID>-tfstate`).
- API enablements (cost nothing when no resource exists).
- Local artifacts (`infra/tfplan`, `pipeline/data_job/dataform/workflow_settings.yaml`,
  `.venv`) — `make clean` covers these.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts._common import env, run
from scripts.local.setup.seed_minimal_clean import main as seed_clean_main

INFRA = Path(__file__).resolve().parents[3] / "infra" / "terraform" / "environments" / "dev"
MANIFESTS = Path(__file__).resolve().parents[3] / "infra" / "manifests"

# Resource addresses for the BQ tables that carry deletion_protection.
# Kept in sync with infra/terraform/modules/data/main.tf — if a new protected table
# is added, append it here.
PROTECTED_TABLE_TARGETS = [
    "module.data.google_bigquery_table.training_runs",
    "module.data.google_bigquery_table.search_logs",
    "module.data.google_bigquery_table.ranking_log",
    "module.data.google_bigquery_table.feedback_events",
    "module.data.google_bigquery_table.validation_results",
    "module.data.google_bigquery_table.property_features_daily",
    "module.data.google_bigquery_table.property_embeddings",
    # Phase 6 は Vertex Monitoring v2 縮退で `model_monitoring_alerts` を
    # 作らない見込みだが、過去 resource がある環境で destroy を冪等に回すため
    # リストに残しておく (不在 table への `-target` は Terraform 側で no-op)。
    "module.data.google_bigquery_table.model_monitoring_alerts",
]

# Terraform-managed GCS buckets that have `force_destroy = false` hardcoded.
# Any object left in these blocks `terraform destroy` with
# "containing objects without `force_destroy` set to true". Suffixes match
# defaults in infra/terraform/modules/{data,meilisearch}/main.tf (bucket
# name = "${project_id}-${suffix}").
BUCKET_SUFFIXES = [
    "models",
    "artifacts",
    "pipeline-root",
    "meili-data",
]

# Namespaces created by KServe + search-api manifests. cert-manager ships with
# KServe as a prerequisite Helm release (infra/terraform/modules/kserve/main.tf)
# and sometimes leaves finalizers pinning the namespace.
K8S_NAMESPACES = ["search", "kserve-inference", "cert-manager", "kserve"]


def _step(num: int, total: int, msg: str) -> None:
    print(f"==> [{num}/{total}] {msg}", flush=True)


def _info(msg: str) -> None:
    print(f"    {msg}", flush=True)


def _warn(msg: str) -> None:
    print(f"    [warn] {msg}", file=sys.stderr, flush=True)


def _kubectl_available() -> bool:
    """Detect whether kubectl has a reachable current-context.

    destroy-all should still work even if the cluster is already gone or
    kubeconfig is not initialized (e.g. fresh machine running destroy against
    a previously-broken deploy). Any non-zero from `kubectl cluster-info`
    means we skip the K8s cleanup steps and let terraform destroy deal with
    whatever is left.
    """
    proc = subprocess.run(
        ["kubectl", "cluster-info"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode == 0


def _kubectl_drain_manifests() -> None:
    """Remove Deployment / InferenceService / Gateway / NetworkPolicy etc.
    via `kubectl delete -k` so GKE-side resources don't block terraform destroy."""
    if not MANIFESTS.exists():
        _warn(f"manifests dir {MANIFESTS} absent — skip")
        return
    _info(f"kubectl delete -k {MANIFESTS} --ignore-not-found --wait=true")
    run(
        [
            "kubectl",
            "delete",
            "-k",
            str(MANIFESTS),
            "--ignore-not-found",
            "--wait=true",
        ],
        check=False,
    )


def _kubectl_delete_namespace(ns: str) -> None:
    _info(f"kubectl delete namespace {ns} --ignore-not-found --wait=false")
    run(
        [
            "kubectl",
            "delete",
            "namespace",
            ns,
            "--ignore-not-found",
            "--wait=false",
        ],
        check=False,
    )


def _wipe_bucket(project_id: str, bucket: str) -> None:
    """Recursively delete every object in one GCS bucket. Benign on absence."""
    uri = f"gs://{bucket}"
    _info(f"wipe {uri} (gcloud storage rm --recursive --quiet {uri}/**)")
    run(
        [
            "gcloud",
            "storage",
            "rm",
            "--recursive",
            f"--project={project_id}",
            "--quiet",
            f"{uri}/**",
        ],
        check=False,
    )


def main() -> int:
    project_id = env("PROJECT_ID")
    github_repo = env("GITHUB_REPO")
    oncall_email = env("ONCALL_EMAIL")

    common_vars = [
        "-var=enable_deletion_protection=false",
        f"-var=github_repo={github_repo}",
        f"-var=oncall_email={oncall_email}",
    ]

    print(f"==> destroy-all on project {project_id!r} (Phase 6 / GKE + KServe)")
    total = 6

    _step(1, total, "seed-test-clean (drop out-of-TF tables that block dataset destroy)")
    seed_clean_main()

    k8s_reachable = _kubectl_available()
    _info(f"kubectl reachable={k8s_reachable}")

    _step(
        2,
        total,
        "kubectl delete -k infra/manifests/ (drain Deployment / InferenceService / Gateway)",
    )
    if k8s_reachable:
        _kubectl_drain_manifests()
    else:
        _warn("kubectl not reachable — skip manifest drain (cluster may already be gone)")

    _step(
        3,
        total,
        f"kubectl delete namespace {K8S_NAMESPACES} (force-remove any finalizer-stuck ns)",
    )
    if k8s_reachable:
        for ns in K8S_NAMESPACES:
            _kubectl_delete_namespace(ns)
    else:
        _warn("kubectl not reachable — skip namespace delete")

    _step(
        4,
        total,
        f"wipe GCS buckets (force_destroy=false blockers): "
        f"{[f'{project_id}-{s}' for s in BUCKET_SUFFIXES]}",
    )
    for suffix in BUCKET_SUFFIXES:
        _wipe_bucket(project_id, f"{project_id}-{suffix}")

    _step(
        5,
        total,
        f"terraform apply -target=<{len(PROTECTED_TABLE_TARGETS)} BQ tables> "
        "-var=enable_deletion_protection=false (state-flip only, no recreate)",
    )
    targets = [arg for tgt in PROTECTED_TABLE_TARGETS for arg in ("-target", tgt)]
    run(
        [
            "terraform",
            f"-chdir={INFRA}",
            "apply",
            "-auto-approve",
            *common_vars,
            *targets,
        ],
        check=False,  # some targets may be absent (e.g. model_monitoring_alerts in Phase 6)
    )

    _step(6, total, "terraform destroy -auto-approve")
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
