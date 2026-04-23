"""KFP component: upload and optionally deploy a reranker model."""

from kfp import dsl


@dsl.component(
    base_image="python:3.12",
    packages_to_install=["google-cloud-aiplatform>=1.71,<2"],
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
    model_artifact: dsl.Input[dsl.Model],
) -> str:
    # --- entry log (must appear even if later imports fail) ---
    import sys
    import traceback

    def _log(msg: str) -> None:
        # stdout + stderr の両方に出し、Cloud Logging の取りこぼしを最小化
        print(f"[register_reranker] {msg}", flush=True)
        print(f"[register_reranker] {msg}", file=sys.stderr, flush=True)

    _log("STEP 1 — component entry")
    _log(f"  python={sys.version}")
    _log(f"  project_id={project_id} vertex_location={vertex_location}")
    _log(f"  model_display_name={model_display_name}")
    _log(f"  endpoint_resource_name={endpoint_resource_name!r}")
    _log(f"  serving_container_image_uri={serving_container_image_uri}")
    _log(f"  service_account={service_account!r}")
    _log(f"  traffic_new_percentage={traffic_new_percentage}")
    _log(f"  deploy_machine_type={deploy_machine_type}")
    _log(f"  model_artifact.uri={model_artifact.uri}")
    _log(f"  model_artifact.path={model_artifact.path}")
    _log(f"  model_artifact.metadata={model_artifact.metadata}")

    try:
        import os

        _log("STEP 2 — listing model_artifact.path contents")
        p = model_artifact.path
        if os.path.isdir(p):
            _log("  path is a DIRECTORY; listing:")
            for entry in os.listdir(p):
                full = os.path.join(p, entry)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = -1
                _log(f"    - {entry} size={size}")
        elif os.path.isfile(p):
            try:
                size = os.path.getsize(p)
            except OSError:
                size = -1
            _log(f"  path is a FILE size={size}")
        else:
            _log("  path does NOT exist on worker filesystem")
    except Exception as e:
        _log(f"  WARN: failed to enumerate model_artifact.path: {e}")

    try:
        _log("STEP 3 — import aiplatform + init")
        from google.cloud import aiplatform

        aiplatform.init(project=project_id, location=vertex_location)
        _log("  aiplatform.init OK")
    except Exception:
        _log("ERROR at STEP 3")
        _log(traceback.format_exc())
        raise

    # train_reranker は model.path を単一ファイル (例: .../model) に書くため、
    # model_artifact.uri は gs://.../model のような OBJECT URI になる。
    # Vertex Model.upload は artifact_uri にディレクトリプレフィックスを期待する
    # ので、親ディレクトリを渡す。
    _log("STEP 4 — derive artifact_uri (directory prefix)")
    if "/" in model_artifact.uri:
        artifact_dir_uri = model_artifact.uri.rsplit("/", 1)[0] + "/"
    else:
        artifact_dir_uri = model_artifact.uri
    _log(f"  artifact_dir_uri={artifact_dir_uri}")

    try:
        _log("STEP 5 — aiplatform.Model.upload")
        uploaded_model = aiplatform.Model.upload(
            display_name=model_display_name,
            artifact_uri=artifact_dir_uri,
            serving_container_image_uri=serving_container_image_uri,
            serving_container_predict_route="/predict",
            serving_container_health_route="/health",
            serving_container_ports=[8080],
            version_aliases=["staging"],
            sync=True,
        )
        _log(f"  Model.upload OK: resource_name={uploaded_model.resource_name}")
        _log(f"  version_id={uploaded_model.version_id}")
    except Exception:
        _log("ERROR at STEP 5 (Model.upload)")
        _log(traceback.format_exc())
        raise

    if endpoint_resource_name:
        try:
            _log(f"STEP 6 — deploy to endpoint {endpoint_resource_name}")
            endpoint = aiplatform.Endpoint(endpoint_name=endpoint_resource_name)
            uploaded_model.deploy(
                endpoint=endpoint,
                deployed_model_display_name=model_display_name,
                machine_type=deploy_machine_type,
                min_replica_count=1,
                max_replica_count=5,
                traffic_percentage=traffic_new_percentage,
                service_account=service_account or None,
                sync=True,
            )
            _log("  deploy OK")
        except Exception:
            _log("ERROR at STEP 6 (Endpoint.deploy)")
            _log(traceback.format_exc())
            raise
    else:
        _log("STEP 6 — skipped (endpoint_resource_name is empty)")

    _log(f"DONE — returning resource_name={uploaded_model.resource_name}")
    return str(uploaded_model.resource_name)
