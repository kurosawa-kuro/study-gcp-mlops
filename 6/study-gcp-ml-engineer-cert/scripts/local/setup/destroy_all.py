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
   -target=<each-table>` — flip every BQ table's `deletion_protection` to
   false in Terraform state. `-target` is **load-bearing**: a bare apply
   would also try to (re)create any resource that drifted out of state
   from a previous half-destroy (e.g. SAs whose IAM bindings linger as
   `deleted:serviceaccount:...?uid=...` in dataset IAM policies). Limiting
   apply to the 8 BQ tables guarantees this state-flip is a pure attribute
   change, no resource (re)creation.
5. `terraform destroy -auto-approve` — actually tears infra down. The
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
from scripts.local.setup.seed_minimal_clean import main as seed_clean_main

INFRA = Path(__file__).resolve().parents[3] / "infra" / "terraform" / "environments" / "dev"

# Resource addresses for the 8 BQ tables that carry deletion_protection.
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
    "module.data.google_bigquery_table.model_monitoring_alerts",
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

    print("==> [1/5] seed-test-clean (drop out-of-TF tables that block dataset destroy)")
    seed_clean_main()

    print(
        f"==> [2/5] undeploy Vertex endpoint deployed_models "
        f"(region={region}, endpoints={VERTEX_ENDPOINTS})"
    )
    for endpoint in VERTEX_ENDPOINTS:
        _undeploy_endpoint_models(project_id, region, endpoint)

    print(
        f"==> [3/5] wipe GCS buckets (force_destroy=false blockers): "
        f"{[f'{project_id}-{s}' for s in BUCKET_SUFFIXES]}"
    )
    for suffix in BUCKET_SUFFIXES:
        _wipe_bucket(project_id, f"{project_id}-{suffix}")

    print(
        "==> [4/5] terraform apply -target=<8 BQ tables> "
        "-var=enable_deletion_protection=false (state-flip only, no recreate)"
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
        ]
    )

    print("==> [5/5] terraform destroy -auto-approve")
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
