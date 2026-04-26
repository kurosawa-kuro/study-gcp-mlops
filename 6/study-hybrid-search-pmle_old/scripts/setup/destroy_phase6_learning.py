"""Lightweight teardown for Phase 6 learning sessions.

Destroys only the runtime artifacts + endpoints that accumulate during Phase 6
learning, WITHOUT touching Terraform state or infrastructure. Use this for
coast-down between learning iterations when you want to keep the infrastructure
(Terraform, BigQuery, etc.) but reclaim GCS / Vertex resources.

Steps:

1. `gcloud ai endpoints undeploy-model` — remove deployed models from encoder + reranker endpoints
   (benign if endpoints absent or already empty)
2. `gcloud storage rm --recursive gs://mlops-dev-a-models/*` — wipe model artifacts
3. `gcloud storage rm --recursive gs://mlops-dev-a-artifacts/*` — wipe encoder assets

Unlike destroy-all, does NOT touch:
- Terraform state / infrastructure (SAs, datasets, topics, etc.)
- Endpoints themselves (empty shells preserved for next learning session)
- BQ tables (preserved for next run)
- tfstate bucket

Post-cleanup, re-running `make deploy-all` will re-provision only the learning-time
artifacts (models, assets, deployed_models), saving ~5-10 min vs full destroy-all.

Usage:
  make destroy-phase6-learning    # dry-run: lists resources to be deleted
  APPLY=1 make destroy-phase6-learning  # actually deletes
"""

from __future__ import annotations

import json
import os
import subprocess

from scripts._common import env, run


def _step(n: int, label: str) -> None:
    apply_mode = os.getenv("APPLY", "0") == "1"
    print()
    print(f"[destroy-phase6-learning] step {n}: {label}")
    if not apply_mode:
        print("  (dry-run mode; pass APPLY=1 to execute)")


def _gcloud_capture(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["gcloud", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def main() -> int:
    apply_mode = os.getenv("APPLY", "0") == "1"
    
    try:
        project_id = env("PROJECT_ID")
        vertex_location = env("VERTEX_LOCATION", "asia-northeast1")
    except Exception as e:
        print(f"❌ Error loading environment: {e}")
        print("   Ensure env/config/setting.yaml is present and configured.")
        return 1
    
    # Vertex Endpoint resource IDs (must match infra/terraform/modules/vertex/main.tf)
    encoder_endpoint_id = "property-encoder-endpoint"
    reranker_endpoint_id = "property-reranker-endpoint"
    
    # GCS buckets to wipe
    models_bucket = f"gs://{project_id}-models"
    artifacts_bucket = f"gs://{project_id}-artifacts"

    print()
    print("=" * 70)
    print("destroy-phase6-learning: Coast-down learning-time artifacts only")
    print("=" * 70)

    # Step 1: Undeploy models from endpoints
    _step(1, "undeploy encoder/reranker endpoints")

    for endpoint_name in [encoder_endpoint_id, reranker_endpoint_id]:
        print(f"  → {endpoint_name} (getting deployed model IDs...)")

        rc, desc_json = _gcloud_capture([
            "ai",
            "endpoints",
            "describe",
            endpoint_name,
            f"--location={vertex_location}",
            f"--project={project_id}",
            "--format=json",
        ])

        if rc != 0:
            print(f"    ⚠ Endpoint not found (benign). Skipping.")
            continue

        # Extract deployedModels from JSON
        try:
            desc = json.loads(desc_json)
            deployed_models = desc.get("deployedModels", [])
            
            if not deployed_models:
                print(f"    ✓ No deployed models (already empty).")
                continue
            
            for dm in deployed_models:
                model_id = dm.get("id")
                print(f"    → Undeploying deployed model id={model_id}...")
                
                if apply_mode:
                    run([
                        "gcloud",
                        "ai",
                        "endpoints",
                        "undeploy-model",
                        endpoint_name,
                        f"--deployed-model-id={model_id}",
                        f"--location={vertex_location}",
                        f"--project={project_id}",
                        "--quiet",
                    ])
                    print(f"      ✓ Undeployed.")
                else:
                    print(f"      (dry-run: would undeploy)")
        except Exception as e:
            print(f"    ⚠ Error parsing endpoint: {e}. Skipping.")

    # Step 2: Wipe GCS model artifacts
    _step(2, f"wipe {models_bucket}/**")

    rc, stat_output = _gcloud_capture(["storage", "stat", models_bucket])
    if rc == 0:
        print(f"  → Bucket exists. Listing objects...")
        rc, ls_output = _gcloud_capture(["storage", "ls", "-r", f"{models_bucket}/"])
        if rc == 0 and ls_output.strip():
            obj_count = len(ls_output.strip().split("\n"))
            print(f"    Found {obj_count} objects.")
            
            if apply_mode:
                print(f"    Deleting...")
                run([
                    "gcloud",
                    "storage",
                    "rm",
                    "--recursive",
                    "--quiet",
                    f"{models_bucket}/**",
                ], check=False)
                print(f"    ✓ Deleted.")
            else:
                print(f"    (dry-run: would delete {obj_count} objects)")
        else:
            print(f"    ✓ Bucket empty.")
    else:
        print(f"  ⚠ Bucket not found (benign). Skipping.")

    # Step 3: Wipe GCS encoder assets
    _step(3, f"wipe {artifacts_bucket}/**")

    rc, stat_output = _gcloud_capture(["storage", "stat", artifacts_bucket])
    if rc == 0:
        print(f"  → Bucket exists. Listing objects...")
        rc, ls_output = _gcloud_capture(["storage", "ls", "-r", f"{artifacts_bucket}/"])
        if rc == 0 and ls_output.strip():
            obj_count = len(ls_output.strip().split("\n"))
            print(f"    Found {obj_count} objects.")
            
            if apply_mode:
                print(f"    Deleting...")
                run([
                    "gcloud",
                    "storage",
                    "rm",
                    "--recursive",
                    "--quiet",
                    f"{artifacts_bucket}/**",
                ], check=False)
                print(f"    ✓ Deleted.")
            else:
                print(f"    (dry-run: would delete {obj_count} objects)")
        else:
            print(f"    ✓ Bucket empty.")
    else:
        print(f"  ⚠ Bucket not found (benign). Skipping.")

    print()
    if not apply_mode:
        print("✓ Dry-run complete. To actually destroy, run:")
        print("  APPLY=1 make destroy-phase6-learning")
    else:
        print("✓ destroy-phase6-learning complete.")
        print("  To verify endpoints are empty:")
        print(f"    gcloud ai endpoints describe {encoder_endpoint_id} --location={vertex_location}")
        print(f"    gcloud ai endpoints describe {reranker_endpoint_id} --location={vertex_location}")
        print()
        print("  To re-provision (without Terraform re-apply):")
        print("    make setup-encoder-endpoint APPLY=1")
        print("    make setup-reranker-endpoint APPLY=1")
    print()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
