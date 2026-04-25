"""Smoke-test the Phase 6 T7 副経路: Vertex AI Search (Discovery Engine).

Hits the Discovery Engine ``SearchService.search`` directly with the
configured engine_id / serving_config — bypassing the search-api so
config issues are not masked by Phase 7's Meili fallback.

Usage::

    VERTEX_AGENT_BUILDER_ENGINE_ID=...
    QUERY="新宿 1LDK" make ops-vertex-agent-builder

Exit codes:
    0  — search returned ≥ 1 result
    1  — config missing or empty result set
"""

from __future__ import annotations

import os

from scripts._common import env, fail


def main() -> int:
    project_id = env("PROJECT_ID")
    location = env("VERTEX_AGENT_BUILDER_LOCATION", "global")
    engine_id = env("VERTEX_AGENT_BUILDER_ENGINE_ID")
    collection = env("VERTEX_AGENT_BUILDER_COLLECTION_ID", "default_collection")
    serving_config = env("VERTEX_AGENT_BUILDER_SERVING_CONFIG_ID", "default_search")
    query = os.environ.get("QUERY", "新宿 1LDK")
    page_size = int(os.environ.get("PAGE_SIZE", "5"))

    if not (project_id and engine_id):
        return fail("vertex-agent-builder: PROJECT_ID / VERTEX_AGENT_BUILDER_ENGINE_ID required")

    try:
        from google.cloud import discoveryengine_v1 as discoveryengine
    except ImportError:
        return fail(
            "vertex-agent-builder: google-cloud-discoveryengine not installed. "
            "Add to pyproject.toml dependencies if you intend to verify Agent Builder."
        )

    client = discoveryengine.SearchServiceClient()
    serving_config_path = (
        f"projects/{project_id}/locations/{location}/collections/{collection}/"
        f"engines/{engine_id}/servingConfigs/{serving_config}"
    )
    request = discoveryengine.SearchRequest(
        serving_config=serving_config_path,
        query=query,
        page_size=page_size,
    )
    try:
        response = client.search(request=request)
    except Exception as exc:
        return fail(f"vertex-agent-builder: search failed: {exc}")

    rows = list(response.results)
    print(f"vertex-agent-builder: query={query!r} → {len(rows)} result(s)")
    for r in rows[:page_size]:
        doc_id = getattr(r, "id", "-")
        print(f"  doc_id={doc_id}")

    if not rows:
        return fail(
            "vertex-agent-builder: 0 results. Check engine_id, data store ingestion "
            "(properties_cleaned synced), and serving_config_id."
        )
    print("vertex-agent-builder PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
