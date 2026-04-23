"""Promote a registered Vertex Model Registry version to production (Phase 6).

Phase 6 uses KServe instead of Vertex Endpoint. Promotion is therefore a
Model Registry alias flip only — the actual serving rollout is picked up by
`scripts/local/deploy/kserve_models.py`, which patches the InferenceService
`storageUri` to the `production` alias artifact.

Usage:
    python -m scripts.local.ops.promote reranker v3
    python -m scripts.local.ops.promote reranker v3 --apply
"""

from __future__ import annotations

import argparse
import json

from google.cloud import aiplatform

from scripts._common import env


def build_promotion_plan(model_kind: str, version_alias: str) -> dict[str, str]:
    project_id = env("PROJECT_ID")
    location = env("VERTEX_LOCATION", env("REGION"))
    display_name = env(
        "RERANKER_DISPLAY_NAME" if model_kind == "reranker" else "ENCODER_DISPLAY_NAME",
        "property-reranker" if model_kind == "reranker" else "property-encoder",
    )
    return {
        "project_id": project_id,
        "location": location,
        "display_name": display_name,
        "version_alias": version_alias,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Flip Vertex Model Registry 'production' alias")
    parser.add_argument("model_kind", choices=["reranker", "encoder"])
    parser.add_argument("version_alias")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    plan = build_promotion_plan(args.model_kind, args.version_alias)
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    aiplatform.init(project=plan["project_id"], location=plan["location"])
    models = aiplatform.Model.list(filter=f'display_name="{plan["display_name"]}"')
    matched = None
    for model in models:
        aliases = getattr(model, "version_aliases", []) or []
        if args.version_alias in aliases or model.display_name.endswith(args.version_alias):
            matched = model
            break
    if matched is None:
        raise RuntimeError(f"model alias not found: {args.version_alias}")

    matched.add_version_aliases(["production"])
    print(
        json.dumps(
            {
                "promoted_model": matched.resource_name,
                "version_id": matched.version_id,
                **plan,
                "next": "run scripts/local/deploy/kserve_models.py to roll out to KServe",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
