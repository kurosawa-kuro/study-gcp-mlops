"""End-to-end teardown of every Terraform-managed resource. **No interactive
prompt** — this is a learning / PDCA dev project (`mlops-dev-a`) where fast
iteration matters. Pair with `deploy-all` for a build-test-destroy loop.

Steps:

1. `bq rm -f feature_mart.properties_cleaned` — drop the out-of-Terraform-state
   table that `make seed-test` (`scripts/setup/seed_minimal.py`) creates. It
   blocks `feature_mart` dataset destroy with `resourceInUse` otherwise.
   `check=False` makes this benign when the table is absent.
2. `gcloud ai endpoints undeploy-model` — Terraform-managed
   `google_vertex_ai_endpoint` is an empty shell; `aiplatform.Model.deploy()`
   (KFP components / scripts/setup/*) mutates `deployedModels` server-side.
   Any remaining DeployedModel blocks `terraform destroy` with HTTP 400
   "Endpoint has deployed or being-deployed DeployedModel(s)". Enumerate and
   undeploy synchronously before destroy. Benign when the endpoint is absent
   or already empty.
3. `gcloud storage rm --recursive` on the 4 Terraform-managed buckets
   (models / artifacts / pipeline-root / meili-data). All have
   `force_destroy = false` hardcoded, so terraform destroy fails with
   "containing objects without `force_destroy` set to true" when any of
   them hold objects from a prior run. Wiping is pragmatic: destroy-all is
   a learn/PDCA target where losing model artifacts + pipeline roots is
   intended. Benign when the bucket is absent.
4. `terraform apply -auto-approve -var=enable_deletion_protection=false
   -target=<each>` — flip `deletion_protection` to false on every
   server-side-protected resource currently **in state**
   (`PROTECTED_TARGETS`: 10 BQ tables + 1 GKE cluster, filtered by
   `_filter_targets_in_state` so already-destroyed resources are skipped
   — without that filter `-target` pulls in the dependency closure and
   *recreates* the targets, hitting WIF pool soft-delete on re-run.
   Phase 7 Run 4 fix). `-target` is **load-bearing**: a bare apply would
   also try to (re)create any resource that drifted out of state from a
   previous half-destroy (e.g. SAs whose IAM bindings linger as
   `deleted:serviceaccount:...?uid=...`). The GKE cluster was added in
   Phase 7 Run 4 — without flipping it server-side first the body
   destroy fails with `Cannot destroy cluster because deletion_protection
   is set to true.`
5. `terraform destroy -target=module.kserve` — K8s / Helm リソース
   (`helm_release.{cert_manager,external_secrets}` / `kubernetes_namespace.*`
   / `kubernetes_service_account.*`) を **GKE cluster より先に** 個別 destroy。
   `provider.tf` の `kubernetes` / `helm` provider が
   `data.google_container_cluster.hybrid_search` の endpoint / token に
   依存しているため、cluster が destroy 過程で先に消えると provider が
   `http://localhost:80` に fallback して
   `connection refused` で fail する。先に K8s リソースを片付ければ
   step 6 の本体 destroy 時には provider が一切 cluster API を叩かない。
   targeted destroy 自体が fail した場合 (= cluster が既に消滅していた場合)
   は `terraform state rm` で K8s 系の state を剥がして次に進む。
6. `terraform destroy -auto-approve` — actually tears infra down. The
   var is passed again so Terraform's destroy-time guard sees
   deletion_protection=false.

What this does NOT touch (preserved for the next `make deploy-all`):

- The tfstate bucket (`<PROJECT_ID>-tfstate`).
- API enablements (cost nothing when no resource exists).
- Local artifacts (`infra/tfplan`, `pipeline/data_job/dataform/workflow_settings.yaml`,
  `.venv`) — `make clean` covers these.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts._common import env, run
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
# - Phase 7 Run 4 で **GKE cluster** を追加 (root TF var
#   `enable_deletion_protection` は `infra/terraform/modules/gke/main.tf` の
#   `deletion_protection = var.deletion_protection` に配線済だが、`-target`
#   で flip しないと server-side が `true` のまま残り、本体 destroy が
#   `Cannot destroy cluster because deletion_protection is set to true.`
#   で fail していた)。9 → 10
PROTECTED_TARGETS = [
    "module.data.google_bigquery_table.training_runs",
    "module.data.google_bigquery_table.search_logs",
    "module.data.google_bigquery_table.ranking_log",
    "module.data.google_bigquery_table.feedback_events",
    "module.data.google_bigquery_table.validation_results",
    "module.data.google_bigquery_table.property_features_daily",
    "module.data.google_bigquery_table.property_embeddings",
    "module.data.google_bigquery_table.model_monitoring_alerts",
    "module.data.google_bigquery_table.ranking_log_hourly_ctr",
    "module.gke.google_container_cluster.hybrid_search",
]

# Vertex AI Endpoint resource IDs — these match the `name` fields in
# infra/terraform/modules/vertex/main.tf (hardcoded, not derived from
# display_name). DeployedModels on these must be undeployed before
# `terraform destroy` can delete the endpoint shell resource.
VERTEX_ENDPOINTS = [
    "property-encoder-endpoint",
    "property-reranker-endpoint",
]

# Terraform-managed GCS buckets that have `force_destroy = false` hardcoded.
# Any object left in these blocks `terraform destroy` with
# "containing objects without `force_destroy` set to true". Suffixes match
# defaults in infra/terraform/modules/{data,meilisearch}/main.tf (bucket
# name = "${project_id}-${suffix}"). Wiped with `gcloud storage rm --recursive`
# which is benign on missing buckets (check=False).
BUCKET_SUFFIXES = [
    "models",
    "artifacts",
    "pipeline-root",
    "meili-data",
]

# `module.kserve` 配下の K8s / Helm リソースを `terraform destroy` 本体より
# **先に** 個別 destroy するための target。`infra/terraform/environments/dev/provider.tf`
# の `kubernetes` / `helm` provider は `data.google_container_cluster.hybrid_search`
# (GKE cluster の endpoint / token) に依存しており、cluster が destroy 過程で
# 先に消えると provider が `localhost:80` に fallback して
#   Error: Get "http://localhost/api/v1/namespaces/...": connection refused
#   Error: Kubernetes cluster unreachable: invalid configuration
# で fail する。`-target=module.kserve` (module 全体) を先に destroy して
# K8s/Helm 系を状態から消し、本体 destroy 時に provider が一切 cluster API を
# 叩かない (state に対象が残っていない) 状態にしてから cluster を削除する。
#
# `module.kserve` を **module 単位で指定** することで、新規に
# `helm_release.<name>` / `kubernetes_*` を追加した時の取りこぼしを防ぐ
# (Phase 7 Run 4 で `helm_release.kserve_crd` / `helm_release.kserve` が
# 個別列挙から漏れて step 5/6 が no-op になり step 6/6 で fail した教訓)。
KSERVE_MODULE_TARGET = "module.kserve"


def _kserve_state_remaining(infra_dir: Path) -> list[str]:
    """Return module.kserve に紐づく state アドレスの list (空なら片付け済)。

    `terraform state list` が module 配下のすべての resource address を行単位で
    返すので、それを `module.kserve.` prefix で grep する。`-target` destroy が
    exit 0 でも cluster unreachable で実は何も消えなかったケース (Phase 7
    Run 4 の `helm_release.kserve_crd` 取りこぼし) を **exit code でなく
    state そのもの** で検知するための後方確認に使う。
    """
    proc = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "state", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    prefix = f"{KSERVE_MODULE_TARGET}."
    return [line for line in proc.stdout.splitlines() if line.startswith(prefix)]


def _state_size(infra_dir: Path) -> int:
    """Return the number of address lines in `terraform state list`.

    Used to skip the destroy pipeline when the previous run already cleared
    everything (idempotent destroy-all). Without this guard, re-running
    `make destroy-all` on an empty state walks step 4/6 into a `-target`
    apply that **recreates** the targeted resources (dependency closure)
    and tends to crash on WIF pool 30-day soft-delete (ADR 0003).
    """
    proc = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "state", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return 0
    return sum(1 for line in proc.stdout.splitlines() if line.strip())


def _filter_targets_in_state(infra_dir: Path, candidates: list[str]) -> list[str]:
    """Filter ``candidates`` to keep only addresses that actually exist in
    the current state.

    Step 4/6 declares "state-flip only, no recreate" — to honour that we
    must not pass a `-target` for a resource missing from state, otherwise
    Terraform pulls in its full dependency closure and creates fresh
    instances of dependencies. Pre-filtering keeps the apply truly
    no-op-ish on resources already destroyed by a previous run.
    """
    proc = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "state", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    in_state = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    return [t for t in candidates if t in in_state]


def _state_rm_kserve_resources(infra_dir: Path) -> None:
    """Remove **all** module.kserve entries from state.

    Used as a fallback when targeted destroy could not actually clear the
    K8s/Helm resources (cluster unreachable, or new resource added that we
    forgot to enumerate). `terraform state rm` accepts a module address so
    we can wipe everything under `module.kserve` in one shot — the next
    full destroy will not try to call the K8s API.
    """
    remaining = _kserve_state_remaining(infra_dir)
    if not remaining:
        print("    module.kserve in state: empty (nothing to rm)")
        return
    print(f"    module.kserve in state: {len(remaining)} address(es) → state rm")
    for address in remaining:
        print(f"      {address}")
    proc = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "state", "rm", KSERVE_MODULE_TARGET],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        print("    state rm module.kserve: OK")
    else:
        # tail of stderr is enough — full output spams the destroy log.
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        print(f"    state rm module.kserve: failed — {' / '.join(tail)}")


def _undeploy_endpoint_models(project_id: str, region: str, endpoint: str) -> None:
    """Synchronously undeploy every DeployedModel on one endpoint.

    Benign when the endpoint does not exist yet (fresh project / already
    torn down) — we detect that via `gcloud describe` returning non-zero.
    `gcloud ... undeploy-model --quiet` waits for the long-running op,
    so control returns only when the deployed_model is fully detached.
    """
    proc = subprocess.run(
        [
            "gcloud",
            "ai",
            "endpoints",
            "describe",
            endpoint,
            f"--region={region}",
            f"--project={project_id}",
            "--format=json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"    endpoint {endpoint!r} not present — skip")
        return
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    deployed = payload.get("deployedModels") or []
    if not deployed:
        print(f"    endpoint {endpoint!r} has no deployed_models — skip")
        return
    for dm in deployed:
        dm_id = dm["id"]
        display = dm.get("displayName", "?")
        print(f"    undeploy-model {endpoint} id={dm_id} display={display}")
        run(
            [
                "gcloud",
                "ai",
                "endpoints",
                "undeploy-model",
                endpoint,
                f"--deployed-model-id={dm_id}",
                f"--region={region}",
                f"--project={project_id}",
                "--quiet",
            ]
        )


def _wipe_bucket(project_id: str, bucket: str) -> None:
    """Recursively delete every object in one GCS bucket. Benign on absence.

    `gcloud storage rm --recursive gs://BUCKET/**` returns non-zero when the
    bucket doesn't exist or is already empty — both outcomes are fine here,
    so we suppress the error.
    """
    uri = f"gs://{bucket}"
    print(f"    wipe {uri}")
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
    region = env("VERTEX_LOCATION") or env("REGION")
    github_repo = env("GITHUB_REPO")
    oncall_email = env("ONCALL_EMAIL")

    common_vars = [
        "-var=enable_deletion_protection=false",
        f"-var=github_repo={github_repo}",
        f"-var=oncall_email={oncall_email}",
    ]

    print(f"==> destroy-all on project {project_id!r}")

    # 既に state が空なら destroy は何もすることがない。`-target` apply が
    # 依存ごと resource を recreate してしまう副作用 (Phase 7 Run 4 で
    # WIF pool 30 日 soft-delete に再衝突した事故) を避けるため early-return。
    state_count = _state_size(INFRA)
    if state_count == 0:
        print("==> state list is empty — nothing to destroy. (前回の destroy-all で完了済)")
        print("    Re-provision with: make deploy-all")
        return 0
    print(f"==> state has {state_count} address(es) — proceeding")

    print("==> [1/6] seed-test-clean (drop out-of-TF tables that block dataset destroy)")
    seed_clean_main()

    print(
        f"==> [2/6] undeploy Vertex endpoint deployed_models "
        f"(region={region}, endpoints={VERTEX_ENDPOINTS})"
    )
    for endpoint in VERTEX_ENDPOINTS:
        _undeploy_endpoint_models(project_id, region, endpoint)

    print(
        f"==> [3/6] wipe GCS buckets (force_destroy=false blockers): "
        f"{[f'{project_id}-{s}' for s in BUCKET_SUFFIXES]}"
    )
    for suffix in BUCKET_SUFFIXES:
        _wipe_bucket(project_id, f"{project_id}-{suffix}")

    # state に実存する PROTECTED_TARGETS のみ flip 対象に。state にないものを
    # `-target` で渡すと Terraform は依存閉包を pull して **recreate** に走る
    # (Phase 7 Run 4 で empty-state の destroy-all 再走 → 12 resources added の
    # 事故)。filter で「flip だけ」に絞る。
    flip_targets = _filter_targets_in_state(INFRA, list(PROTECTED_TARGETS))
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
    # 残ってる、というケースが起きうる (Phase 7 Run 4 で観測)。
    # 後方確認として `terraform state list` で残存を直接見る。
    remaining = _kserve_state_remaining(INFRA)
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
        _state_rm_kserve_resources(INFRA)

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
