"""Resolve live Meilisearch URL → search-api ConfigMap overlay.

`infra/manifests/search-api/configmap.example.yaml` は
``meili_base_url: https://meili-search-XXXXX-an.a.run.app`` placeholder の
まま `kubectl apply -k` で入る (環境別 overlay を意図した名前)。PDCA loop
では fresh deploy のたびに Cloud Run URL の suffix が変わり得るので、
``gcloud run services describe meili-search`` の値で動的に上書きする。
本 step は **deploy-api より前**に走らせること: deploy-api の
``kubectl set image`` がトリガする新 Pod が起動時に最新 ConfigMap を読む
ことで、placeholder URL を引いて 404 → lexical=0 になる事故を防ぐ。

ConfigMap schema (キー列 / default 値) は ``scripts/lib/config.py`` で
唯一定義されているため、本 module は live 値の解決と kubectl apply
だけを担う。schema 変更は scripts/lib/config.py 側で完結する
(Phase 7 W2-5 で `_run_overlay_configmap` と `sync_configmap.py` が
独立に key を手書きしていた drift バグへの構造的対策)。
"""

from __future__ import annotations

import subprocess

from scripts._common import env, gcs_bucket_name, run
from scripts.lib.config import generate_configmap_data, render_configmap_yaml
from scripts.lib.gcp_resources import MEILI_SERVICE_NAME_DEFAULT


def _resolve_meili_url(project_id: str, region: str) -> str:
    """Look up the Meilisearch Cloud Run service URL via gcloud."""
    service = env("MEILI_SERVICE", MEILI_SERVICE_NAME_DEFAULT)
    proc = run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            service,
            f"--project={project_id}",
            f"--region={region}",
            "--format=value(status.url)",
        ],
        capture=True,
        check=False,
    )
    url = (proc.stdout or "").strip()
    if proc.returncode != 0 or not url:
        raise SystemExit(
            f"[error] {service} Cloud Run URL resolution failed. "
            f"Confirm tf-apply created the service in {project_id}/{region}."
        )
    return url


def main() -> int:
    project_id = env("PROJECT_ID")
    if not project_id:
        raise SystemExit("[error] PROJECT_ID is empty")
    region = env("REGION", "asia-northeast1")
    meili_url = _resolve_meili_url(project_id, region)
    models_bucket = env("MODELS_BUCKET", gcs_bucket_name("models"))
    print(f"[info] resolved meili_base_url={meili_url}")
    print(f"[info] models_bucket={models_bucket}")

    data = generate_configmap_data(
        project_id=project_id,
        models_bucket=models_bucket,
        meili_base_url=meili_url,
    )
    cm_yaml = render_configmap_yaml(data, with_header=False)

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


if __name__ == "__main__":
    raise SystemExit(main())
