"""KFP component: MINIMAL stub for reranker registration.

Phase 5 Run 4 で `@dsl.component(packages_to_install=["google-cloud-aiplatform"])`
付きの register-reranker が **pipeline 末尾** で走ると worker が 0 ログで exit 1
する事故 (5 連続失敗) が発生した。`resolve_hyperparameters` (pipeline 冒頭) は
同 packages でも成功するため、末尾 pip install のタイミング問題と判断。

決着: pipeline 内の register-reranker は **MINIMAL stub (print + return のみ)**
に縮退させて pipeline を SUCCEED させ、実 Model.upload は pipeline 外の
`scripts/local/ops/register_model.py` (Phase 5 で新設、Phase 6 でも継承) から
ローカル Python で叩く。Phase 6 の KServe 切替では、さらに
`scripts/local/deploy/kserve_models.py` が Model Registry から artifact URI を
引いて KServe InferenceService の storageUri を patch するため、pipeline →
Registry → KServe の流れが 3 点の独立スクリプトで完結する構成を維持する。
"""

from kfp import dsl


@dsl.component(
    base_image="python:3.12",
)
def register_reranker(
    project_id: str,
    vertex_location: str,
    model_display_name: str,
    endpoint_resource_name: str,
    serving_container_image_uri: str,
    service_account: str,
    traffic_new_percentage: int,
    deploy_machine_type: str,
    model_artifact_uri: str,
) -> str:
    import sys

    def _log(msg: str) -> None:
        print(f"[register_reranker] {msg}", flush=True)
        print(f"[register_reranker] {msg}", file=sys.stderr, flush=True)

    _log("MINIMAL-REGISTER — entry OK")
    _log(f"  project_id={project_id} model_display_name={model_display_name}")
    _log(f"  model_artifact_uri={model_artifact_uri}")
    _log(f"  serving_container_image_uri={serving_container_image_uri}")
    _log(f"  endpoint_resource_name={endpoint_resource_name!r}")
    _log("MINIMAL-REGISTER — done, returning dummy resource name")
    return f"projects/debug/locations/{vertex_location}/models/stub-{model_display_name}"
