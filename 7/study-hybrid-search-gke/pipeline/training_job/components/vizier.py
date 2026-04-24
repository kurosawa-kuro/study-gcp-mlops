"""KFP component: resolve hyperparameters, optionally via Vertex Vizier."""

import json

from kfp import dsl


@dsl.component(
    base_image="python:3.12",
    packages_to_install=["google-cloud-aiplatform>=1.71,<2"],
)
def resolve_hyperparameters(
    enabled: bool,
    baseline_hyperparameters_json: str,
    project_id: str,
    vertex_location: str,
    study_display_name: str,
    max_trial_count: int,
    parallel_trial_count: int,
) -> str:
    import sys
    import traceback

    def _log(msg: str) -> None:
        print(f"[resolve_hyperparameters] {msg}", flush=True)
        print(f"[resolve_hyperparameters] {msg}", file=sys.stderr, flush=True)

    _log("STEP 1 — component entry")
    _log(f"  enabled={enabled}")
    _log(f"  baseline_hyperparameters_json={baseline_hyperparameters_json}")
    _log(f"  project_id={project_id} vertex_location={vertex_location}")
    _log(f"  study_display_name={study_display_name}")
    _log(f"  max_trial_count={max_trial_count} parallel_trial_count={parallel_trial_count}")

    if not enabled:
        _log("STEP 2 — tuning disabled, returning baseline")
        return baseline_hyperparameters_json

    try:
        from google.cloud import aiplatform

        baseline = json.loads(baseline_hyperparameters_json)
        aiplatform.init(project=project_id, location=vertex_location)
        _log(f"  aiplatform.init OK; baseline={baseline}")

        # Placeholder for the real Vizier job wiring. Until the custom job spec lands,
        # keep the pipeline contract stable and return the baseline parameters.
        _ = {
            "study_display_name": study_display_name,
            "max_trial_count": max_trial_count,
            "parallel_trial_count": parallel_trial_count,
        }
        _log("STEP 3 — returning baseline (Vizier wiring not yet implemented)")
        return json.dumps(baseline, ensure_ascii=False)
    except Exception:
        _log("ERROR in resolve_hyperparameters")
        _log(traceback.format_exc())
        raise
