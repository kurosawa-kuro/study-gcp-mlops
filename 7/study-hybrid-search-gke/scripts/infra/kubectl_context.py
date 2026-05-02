"""kubeconfig synchronisation for the target GKE cluster.

`terraform apply` がクラスタを作成しても、ローカル kubeconfig が自動で
その cluster を指すわけではない。apply-manifests / overlay-configmap は
`kubectl` を直叩きするため、先に `gcloud container clusters get-credentials`
を流して `current-context` を target cluster に固定する。

Phase 7 Run 5 教訓 — `destroy-all → deploy-all` PDCA loop では cluster を
同じ name で再作成するが、古い kubeconfig には旧 cluster の CA cert +
endpoint IP が残ったまま、context name だけが一致してしまう。これを
skip 条件として `current-context` 一致で early-return すると、次の
`kubectl apply` が `x509: certificate signed by unknown authority` で
fail する。そのため context 一致による skip はせず、**毎回
get-credentials を呼んで kubeconfig を上書き**する (gcloud 側で値が
同じなら no-op に近い fast path、context 一致でも CA / endpoint は
再フェッチして TLS 不一致を解消する)。
"""

from __future__ import annotations

from scripts._common import env, run
from scripts.lib.gcp_resources import GKE_CLUSTER_NAME_DEFAULT


def ensure() -> None:
    """Refresh kubeconfig to target the freshly-provisioned GKE cluster."""
    project_id = env("PROJECT_ID")
    region = env("REGION", "asia-northeast1")
    cluster_name = env("GKE_CLUSTER_NAME", GKE_CLUSTER_NAME_DEFAULT)
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
