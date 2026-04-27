"""End-to-end provisioning + rollout in one shot. Calls (in order):

1. `tf_bootstrap` — enable APIs + create tfstate bucket (idempotent)
2. `tf_init` — terraform init with bucket preflight
3. `_recover_wif_state` — undelete + import WIF pool/provider if a previous
   `make destroy-all` left them soft-deleted (GCP keeps WIF resources for
   30 days after delete; recreating with the same ID otherwise hits HTTP
   409 "already exists")
4. `sync_dataform` — regenerate pipeline/data_job/dataform/workflow_settings.yaml
5. `tf_plan` — terraform plan -out=tfplan (using setting.yaml defaults)
6. `terraform apply tfplan -auto-approve` — apply infra
7. `apply-manifests` — `kubectl apply -k infra/manifests/` (Phase 7 Run 2:
   旧運用は手で `make apply-manifests` を叩く前提だったが、PDCA loop で
   毎回手作業を要求すると `destroy-all → deploy-all` が成立しない。fresh
   cluster 上で Gateway / Deployment / InferenceService / NetworkPolicy /
   PodMonitoring を全部展開する)
8. `overlay-configmap` — search-api ConfigMap の `meili_base_url`
   placeholder (`https://meili-search-XXXXX-an.a.run.app`) を `gcloud run
   services describe meili-search` の実 URL で上書き。これがないと
   search-api → Meilisearch が DNS 失敗で 404 → lexical=0 になる
9. `deploy/api_gke` — Cloud Build + kubectl rollout search-api。
   step 7 が image を `gcr.io/cloudrun/hello` placeholder に戻すので、
   step 8 の ConfigMap 更新後に新しい image でロールアウトする順序が必須

Idempotent — re-running on an already-provisioned project applies a zero-diff
plan and rolls a fresh search-api image revision. Costs accrue from the moment infra is created (Cloud Run
min-instances=1, BQ storage, etc.) — see CLAUDE.md non-negotiables.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scripts._common import env, run
from scripts.ci.sync_dataform import main as sync_dataform_main
from scripts.deploy.api_gke import main as deploy_api_main
from scripts.setup.tf_bootstrap import main as tf_bootstrap_main
from scripts.setup.tf_init import main as tf_init_main
from scripts.setup.tf_plan import main as tf_plan_main

INFRA = Path(__file__).resolve().parents[2] / "infra" / "terraform" / "environments" / "dev"
MANIFESTS = Path(__file__).resolve().parents[2] / "infra" / "manifests"

# Overall start time; per-step timing relates elapsed time to the wall-clock
# position in the deploy-all sequence so operators can see WHICH step is slow
# when a rollout hangs (e.g. Cloud Build wait dominating step 7).
_DEPLOY_ALL_STARTED_AT: float | None = None
_STEP_STARTED_AT: float | None = None


@dataclass(frozen=True)
class DeployStep:
    number: int
    name: str
    label: str
    run: Callable[[], int]


def _step(n: int, total: int, label: str) -> None:
    global _DEPLOY_ALL_STARTED_AT, _STEP_STARTED_AT
    now = time.monotonic()
    # On first step entry, emit a "prev_step_elapsed" anchor of 0 and start
    # the overall clock.
    if _DEPLOY_ALL_STARTED_AT is None:
        _DEPLOY_ALL_STARTED_AT = now
    prev_elapsed = now - _STEP_STARTED_AT if _STEP_STARTED_AT is not None else 0.0
    total_elapsed = now - _DEPLOY_ALL_STARTED_AT
    _STEP_STARTED_AT = now
    print()
    print("================================================================")
    print(f" deploy-all  step {n}/{total}: {label}")
    if n > 1:
        print(f" (prev_step_elapsed={prev_elapsed:.0f}s total_elapsed={total_elapsed:.0f}s)")
    print("================================================================")


def _step_done() -> None:
    """Emit a `step-done` line with elapsed seconds for the step just finished.

    Complements ``_step``: ``_step`` records WHEN a step starts, ``_step_done``
    records HOW LONG it took. Operators (and ``scripts.deploy.monitor``) can
    parse these to locate the slow step in a hung deploy-all.
    """
    if _STEP_STARTED_AT is None:
        return
    elapsed = time.monotonic() - _STEP_STARTED_AT
    print(f" deploy-all  step-done elapsed={elapsed:.0f}s")


def _gcloud_capture(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["gcloud", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def _tf_var_args() -> list[str]:
    return [
        f"-var=github_repo={env('GITHUB_REPO')}",
        f"-var=oncall_email={env('ONCALL_EMAIL')}",
    ]


def _recover_wif_state(project_id: str) -> None:
    """Undelete + import WIF pool/provider if soft-deleted from a prior destroy.

    Detection:
    - Pool: `gcloud iam workload-identity-pools describe github` returns
      `state: DELETED` when soft-deleted.
    - Provider: `gcloud ... providers describe github-oidc` succeeds and
      returns a non-empty `expireTime` only for soft-deleted ones.

    Recovery for each: undelete → `terraform state rm` (in case stale entry)
    → `terraform import` so the next `terraform plan` sees them as
    in-state instead of "to be created" (which would 409).
    """
    pool_args = [
        "iam",
        "workload-identity-pools",
        "describe",
        "github",
        "--location=global",
        f"--project={project_id}",
        "--format=value(state)",
    ]
    rc, pool_state = _gcloud_capture(pool_args)
    if rc == 0 and pool_state == "DELETED":
        print("==> Recovery: undelete soft-deleted WIF pool 'github'")
        run(
            [
                "gcloud",
                "iam",
                "workload-identity-pools",
                "undelete",
                "github",
                "--location=global",
                f"--project={project_id}",
                "--quiet",
            ]
        )
        subprocess.run(
            [
                "terraform",
                f"-chdir={INFRA}",
                "state",
                "rm",
                "module.iam.google_iam_workload_identity_pool.github",
            ],
            check=False,
        )
        run(
            [
                "terraform",
                f"-chdir={INFRA}",
                "import",
                *_tf_var_args(),
                "module.iam.google_iam_workload_identity_pool.github",
                f"projects/{project_id}/locations/global/workloadIdentityPools/github",
            ]
        )

    prov_args = [
        "iam",
        "workload-identity-pools",
        "providers",
        "describe",
        "github-oidc",
        "--workload-identity-pool=github",
        "--location=global",
        f"--project={project_id}",
        "--format=value(expireTime)",
    ]
    rc, expire_time = _gcloud_capture(prov_args)
    if rc == 0 and expire_time:
        print("==> Recovery: undelete soft-deleted WIF provider 'github-oidc'")
        run(
            [
                "gcloud",
                "iam",
                "workload-identity-pools",
                "providers",
                "undelete",
                "github-oidc",
                "--workload-identity-pool=github",
                "--location=global",
                f"--project={project_id}",
                "--quiet",
            ]
        )
        subprocess.run(
            [
                "terraform",
                f"-chdir={INFRA}",
                "state",
                "rm",
                "module.iam.google_iam_workload_identity_pool_provider.github",
            ],
            check=False,
        )
        run(
            [
                "terraform",
                f"-chdir={INFRA}",
                "import",
                *_tf_var_args(),
                "module.iam.google_iam_workload_identity_pool_provider.github",
                f"projects/{project_id}/locations/global/workloadIdentityPools/github/providers/github-oidc",
            ]
        )


def _run_tf_bootstrap() -> int:
    return tf_bootstrap_main()


def _run_tf_init() -> int:
    return tf_init_main()


def _run_recover_wif() -> int:
    _recover_wif_state(env("PROJECT_ID"))
    return 0


def _run_sync_dataform() -> int:
    return sync_dataform_main()


def _run_tf_plan() -> int:
    return tf_plan_main()


def _run_tf_apply() -> int:
    run(["terraform", f"-chdir={INFRA}", "apply", "-auto-approve", "tfplan"])
    return 0


def _ensure_kubectl_context() -> None:
    """Idempotent kubectl context bootstrap for the GKE cluster.

    `terraform apply` がクラスタを作成しても、ローカルの kubeconfig が自動で
    その cluster を指すわけではない。apply-manifests / overlay-configmap は
    `kubectl` を直叩きするため、先に ``gcloud container clusters get-credentials``
    を必要に応じて流して ``current-context`` を target cluster に固定する。
    `scripts.deploy.api_gke._ensure_kubectl_context` と同じロジックの再実装
    (api_gke.py の private helper を import するより、deploy-all 専用の最小版
    をここに置く方が依存方向がきれい)。
    """
    project_id = env("PROJECT_ID")
    region = env("REGION", "asia-northeast1")
    cluster_name = env("GKE_CLUSTER_NAME", "hybrid-search")
    proc = run(["kubectl", "config", "current-context"], capture=True, check=False)
    current = (proc.stdout or "").strip()
    if cluster_name in current:
        print(f"[info] kubectl context already bound to {cluster_name!r} ({current})")
        return
    print(f"==> get-credentials cluster={cluster_name} region={region} project={project_id}")
    run(
        [
            "gcloud",
            "container",
            "clusters",
            "get-credentials",
            cluster_name,
            f"--region={region}",
            f"--project={project_id}",
        ]
    )


def _run_apply_manifests() -> int:
    """`kubectl apply -k infra/manifests/` against the freshly-provisioned cluster.

    Phase 7 Run 2 まで `infra/manifests/README.md §デプロイ` は「Terraform apply
    後に make apply-manifests を手で叩く」運用だった。PDCA dev loop
    (`destroy-all → deploy-all → run-all`) ではこの手作業が成立しないため、
    deploy-all に組み込んで一発で cluster ワークロードを展開する。
    試行錯誤目的の手 apply は引き続き ``make apply-manifests`` で可能。
    """
    _ensure_kubectl_context()
    print(f"==> kubectl apply -k {MANIFESTS}")
    run(["kubectl", "apply", "-k", str(MANIFESTS)])
    return 0


def _run_overlay_configmap() -> int:
    """Resolve the live Meilisearch Cloud Run URL and overwrite ``search-api-config``.

    `infra/manifests/search-api/configmap.example.yaml` は
    `meili_base_url: https://meili-search-XXXXX-an.a.run.app` placeholder の
    まま `kubectl apply -k` で入る (環境別 overlay を意図した名前)。PDCA loop
    では fresh deploy のたびに Cloud Run URL の suffix が変わり得るので、
    `gcloud run services describe meili-search` の値で動的に上書きする。
    本 step は **deploy-api より前**に走らせること: deploy-api の
    `kubectl set image` がトリガする新 Pod が起動時に最新 ConfigMap を読む
    ことで、placeholder URL を引いて 404 → lexical=0 になる事故を防ぐ。
    """
    project_id = env("PROJECT_ID")
    if not project_id:
        raise SystemExit("[error] PROJECT_ID is empty")
    region = env("REGION", "asia-northeast1")
    proc = run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            "meili-search",
            f"--project={project_id}",
            f"--region={region}",
            "--format=value(status.url)",
        ],
        capture=True,
        check=False,
    )
    meili_url = (proc.stdout or "").strip()
    if proc.returncode != 0 or not meili_url:
        raise SystemExit(
            "[error] meili-search Cloud Run URL resolution failed. "
            "Confirm tf-apply created the meili-search service in "
            f"{project_id}/{region}."
        )
    models_bucket = env("MODELS_BUCKET", f"{project_id}-models")
    print(f"[info] resolved meili_base_url={meili_url}")
    print(f"[info] models_bucket={models_bucket}")
    cm_yaml = (
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: search-api-config\n"
        "  namespace: search\n"
        "data:\n"
        f"  project_id: {project_id}\n"
        f"  models_bucket: {models_bucket}\n"
        f"  meili_base_url: {meili_url}\n"
    )
    print("==> kubectl apply -f - (search-api-config ConfigMap overlay)")
    proc = subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=cm_yaml,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"[error] kubectl apply ConfigMap failed rc={proc.returncode}")
    return 0


def _run_deploy_api() -> int:
    return deploy_api_main()


def _steps() -> list[DeployStep]:
    return [
        DeployStep(
            1,
            "tf-bootstrap",
            "tf-bootstrap (enable APIs + tfstate bucket, idempotent)",
            _run_tf_bootstrap,
        ),
        DeployStep(2, "tf-init", "tf-init (preflight + terraform init)", _run_tf_init),
        DeployStep(
            3,
            "recover-wif",
            "recover WIF pool/provider if soft-deleted (PDCA loop safety)",
            _run_recover_wif,
        ),
        DeployStep(
            4,
            "sync-dataform",
            "sync-dataform-config (regenerate workflow_settings.yaml)",
            _run_sync_dataform,
        ),
        DeployStep(5, "tf-plan", "tf-plan (saves infra/tfplan)", _run_tf_plan),
        DeployStep(6, "tf-apply", "terraform apply tfplan -auto-approve", _run_tf_apply),
        DeployStep(
            7,
            "apply-manifests",
            "kubectl apply -k infra/manifests/ (Gateway / Deployment / ISVC / policies)",
            _run_apply_manifests,
        ),
        DeployStep(
            8,
            "overlay-configmap",
            "overlay search-api-config (resolve real meili_base_url)",
            _run_overlay_configmap,
        ),
        DeployStep(
            9,
            "deploy-api",
            "deploy-api (Cloud Build + kubectl rollout search-api)",
            _run_deploy_api,
        ),
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 7 deploy-all flow with optional step slicing."
    )
    parser.add_argument(
        "--from-step",
        default="1",
        help="Start from this step number or name (e.g. 4, sync-dataform, tf-apply).",
    )
    parser.add_argument(
        "--to-step",
        default="9",
        help="Stop after this step number or name (e.g. 7, apply-manifests, deploy-api).",
    )
    return parser.parse_args()


def _resolve_step_ref(ref: str, steps: list[DeployStep]) -> int:
    raw = ref.strip()
    if raw.isdigit():
        step_no = int(raw)
        if any(step.number == step_no for step in steps):
            return step_no
    lowered = raw.lower()
    for step in steps:
        if lowered == step.name:
            return step.number
    valid = ", ".join([str(step.number) for step in steps] + [step.name for step in steps])
    raise SystemExit(f"[error] unknown step {ref!r}. valid values: {valid}")


def main() -> int:
    global _DEPLOY_ALL_STARTED_AT, _STEP_STARTED_AT
    _DEPLOY_ALL_STARTED_AT = None
    _STEP_STARTED_AT = None

    args = _parse_args()
    steps = _steps()
    total = len(steps)
    from_step = _resolve_step_ref(args.from_step, steps)
    to_step = _resolve_step_ref(args.to_step, steps)
    if from_step > to_step:
        raise SystemExit(f"[error] --from-step ({from_step}) must be <= --to-step ({to_step})")

    selected = [step for step in steps if from_step <= step.number <= to_step]
    print(
        f"==> deploy-all selection: from_step={from_step} to_step={to_step} "
        f"steps={[step.name for step in selected]}"
    )

    for step in selected:
        _step(step.number, total, step.label)
        rc = step.run()
        if rc != 0:
            return rc
        _step_done()

    if _DEPLOY_ALL_STARTED_AT is not None:
        total_elapsed = time.monotonic() - _DEPLOY_ALL_STARTED_AT
        print()
        print(f"==> deploy-all complete. total_elapsed={total_elapsed:.0f}s")
    else:
        print()
        print("==> deploy-all complete.")
    print("    Verify with: make ops-livez && make ops-api-url")
    print("    Pipeline submit is separate: make ops-train-now")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
