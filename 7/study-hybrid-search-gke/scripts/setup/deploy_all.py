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
7. `seed-lgbm-model` — `gs://<project>-models/lgbm/latest/model.bst` に
   合成 LightGBM ranker を seed (Phase 7 Run 5: tf-apply 直後の bucket は空で、
   step 8 で apply される `property-reranker` InferenceService の
   storage-initializer init container が ``RuntimeError: Failed to fetch
   model. No model found in gs://...`` で CrashLoopBackOff に陥る。
   reranker pod が Ready にならないと search-api → reranker が 503 →
   `ops-search-components` の rerank=0)
8. `apply-manifests` — `kubectl apply -k infra/manifests/` (Phase 7 Run 2:
   旧運用は手で `make apply-manifests` を叩く前提だったが、PDCA loop で
   毎回手作業を要求すると `destroy-all → deploy-all` が成立しない。fresh
   cluster 上で Gateway / Deployment / InferenceService / NetworkPolicy /
   PodMonitoring を全部展開する)
9. `overlay-configmap` — search-api ConfigMap の `meili_base_url`
   placeholder (`https://meili-search-XXXXX-an.a.run.app`) を `gcloud run
   services describe meili-search` の実 URL で上書き。これがないと
   search-api → Meilisearch が DNS 失敗で 404 → lexical=0 になる
10. `deploy/api_gke` — Cloud Build + kubectl rollout search-api。
   step 8 が image を `gcr.io/cloudrun/hello` placeholder に戻すので、
   step 9 の ConfigMap 更新後に新しい image でロールアウトする順序が必須

Idempotent — re-running on an already-provisioned project applies a zero-diff
plan and rolls a fresh search-api image revision. Costs accrue from the moment infra is created (Cloud Run
min-instances=1, BQ storage, etc.) — see CLAUDE.md non-negotiables.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scripts._common import env, run
from scripts.ci.sync_dataform import main as sync_dataform_main
from scripts.deploy.api_gke import main as deploy_api_main
from scripts.deploy.seed_lgbm_model import main as seed_lgbm_main
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


def _tf_env_for_no_cluster() -> dict[str, str]:
    """Env vars that disable the GKE cluster data source for kubernetes/helm provider init.

    `infra/terraform/environments/dev/provider.tf` の kubernetes/helm
    provider は default で ``data.google_container_cluster.hybrid_search``
    から endpoint / token を引くが、destroy-all 直後の deploy-all では
    cluster 不在で data source が
    ``Error: cluster ... not found`` を返し、provider init ごと
    fallthrough しない resource (terraform import 等) もまとめて落ちる。
    `var.k8s_use_data_source = false` で provider を
    ``https://kubernetes.invalid`` placeholder に切替えて、import 操作
    だけでも空走させる。WIF resource は K8s API を一切叩かないので
    placeholder で問題ない。
    """
    base = os.environ.copy()
    base["TF_VAR_k8s_use_data_source"] = "false"
    return base


def _is_in_tf_state(infra_dir: Path, address: str) -> bool:
    """Return True if ``address`` is currently tracked in Terraform state."""
    proc = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "state", "list"],
        check=False,
        capture_output=True,
        text=True,
        env=_tf_env_for_no_cluster(),
    )
    if proc.returncode != 0:
        return False
    return address in {line.strip() for line in (proc.stdout or "").splitlines()}


def _recover_wif_state(project_id: str) -> None:
    """Reconcile WIF pool / provider with Terraform state.

    GCP の WIF resource は **soft-delete (30 日保持)** で、destroy-all 後に
    同じ ID を再作成しようとすると ``409 Requested entity already exists``
    を返す。回避するには (a) 残存する resource を ``gcloud undelete`` で
    ACTIVE に戻し (b) Terraform state に ``import`` して、次の plan/apply
    で「create」ではなく「変更なし」になるようにする必要がある。

    旧実装は **「state==DELETED の時だけ recover」**だったため、deploy-all
    が部分失敗 → 再実行のシナリオで踏み抜けた事故 (Phase 7 Run 5):
    - 1 回目: undelete 成功 / import 失敗 (cluster data source 不在)
    - 2 回目: WIF state は ACTIVE (= undelete 済) → recover skip →
      tfstate に未 import のまま → ``terraform plan`` が「create」を保存
      → ``terraform apply`` が 409 で fail

    新実装は **「GCP 側に存在する AND tfstate に未登録」** を import 条件
    として、partial-success リトライでも吸収する:
    1. ``gcloud describe`` で resource の現状 (ACTIVE / DELETED / 不在) を取得
    2. DELETED なら undelete (ACTIVE 化)
    3. tfstate に未登録なら ``state rm`` (no-op fallback) → ``import``
    """
    print("==> Recovery: reconcile WIF pool/provider with Terraform state")

    pool_address = "module.iam.google_iam_workload_identity_pool.github"
    pool_id = f"projects/{project_id}/locations/global/workloadIdentityPools/github"
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
    pool_exists_in_gcp = rc == 0 and pool_state in {"ACTIVE", "DELETED"}
    if pool_exists_in_gcp and pool_state == "DELETED":
        print("    pool soft-deleted → undelete to ACTIVE")
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
    if pool_exists_in_gcp and not _is_in_tf_state(INFRA, pool_address):
        print(f"    pool exists in GCP but NOT in tfstate → import {pool_address}")
        subprocess.run(
            ["terraform", f"-chdir={INFRA}", "state", "rm", pool_address],
            check=False,
            env=_tf_env_for_no_cluster(),
        )
        subprocess.run(
            [
                "terraform",
                f"-chdir={INFRA}",
                "import",
                *_tf_var_args(),
                pool_address,
                pool_id,
            ],
            check=True,
            env=_tf_env_for_no_cluster(),
        )

    provider_address = "module.iam.google_iam_workload_identity_pool_provider.github"
    provider_id = (
        f"projects/{project_id}/locations/global/workloadIdentityPools/github/providers/github-oidc"
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
    # provider の `describe` は ACTIVE でも DELETED でも exit 0。`expireTime`
    # フィールドが付いてるのは soft-deleted 状態だけ。describe rc != 0 は
    # 「provider そのものが存在しない (=fresh project / 既に完全消滅)」を意味する。
    provider_exists_in_gcp = rc == 0
    if provider_exists_in_gcp and expire_time:
        print("    provider soft-deleted → undelete to ACTIVE")
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
    if provider_exists_in_gcp and not _is_in_tf_state(INFRA, provider_address):
        print(f"    provider exists in GCP but NOT in tfstate → import {provider_address}")
        subprocess.run(
            ["terraform", f"-chdir={INFRA}", "state", "rm", provider_address],
            check=False,
            env=_tf_env_for_no_cluster(),
        )
        subprocess.run(
            [
                "terraform",
                f"-chdir={INFRA}",
                "import",
                *_tf_var_args(),
                provider_address,
                provider_id,
            ],
            check=True,
            env=_tf_env_for_no_cluster(),
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


def _run_seed_lgbm_model() -> int:
    """Seed a synthetic LightGBM ranker into the models bucket so that the
    `property-reranker` InferenceService's storage-initializer can pull it.

    Phase 7 Run 5: ``destroy-all → deploy-all`` の fresh deploy で
    ``gs://<project>-models/lgbm/latest/`` が空 → reranker pod の
    ``Init:CrashLoopBackOff (Failed to fetch model. No model found ...)``
    → reranker が Ready にならず ``ops-search-components`` の rerank=0。
    apply-manifests (= ISVC create) より前に bucket を埋める。

    実 model は ``ops-train-now`` (run-all-core) で Vertex Pipeline 経由で
    上書きされるが、PDCA dev では合成 model でも reranker pod が Ready に
    なれば 3 経路 smoke の rerank が非ゼロになるので十分。
    """
    return seed_lgbm_main()


def _ensure_kubectl_context() -> None:
    """Bootstrap kubectl context to the freshly-provisioned GKE cluster.

    ``terraform apply`` がクラスタを作成しても、ローカル kubeconfig が自動で
    その cluster を指すわけではない。apply-manifests / overlay-configmap は
    ``kubectl`` を直叩きするため、先に ``gcloud container clusters
    get-credentials`` を流して ``current-context`` を target cluster に固定する。

    Phase 7 Run 5 教訓 — ``destroy-all → deploy-all`` PDCA loop では cluster を
    同じ name で再作成するが、古い kubeconfig には旧 cluster の CA cert +
    endpoint IP が残ったまま、context name だけが一致してしまう。これを
    skip 条件として ``current-context`` 一致で early-return すると、次の
    ``kubectl apply`` が ``x509: certificate signed by unknown authority`` で
    fail する (apply-manifests step 7 で観測)。そのため context 一致による
    skip はせず、**毎回 get-credentials を呼んで kubeconfig を上書き**する
    (gcloud 側で値が同じなら no-op に近い fast path、context 一致でも
    CA / endpoint は再フェッチして TLS 不一致を解消する)。
    """
    project_id = env("PROJECT_ID")
    region = env("REGION", "asia-northeast1")
    cluster_name = env("GKE_CLUSTER_NAME", "hybrid-search")
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
            "seed-lgbm-model",
            "seed gs://<project>-models/lgbm/latest/model.bst (reranker bootstrap)",
            _run_seed_lgbm_model,
        ),
        DeployStep(
            8,
            "apply-manifests",
            "kubectl apply -k infra/manifests/ (Gateway / Deployment / ISVC / policies)",
            _run_apply_manifests,
        ),
        DeployStep(
            9,
            "overlay-configmap",
            "overlay search-api-config (resolve real meili_base_url)",
            _run_overlay_configmap,
        ),
        DeployStep(
            10,
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
        default="10",
        help="Stop after this step number or name (e.g. 8, apply-manifests, deploy-api).",
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
