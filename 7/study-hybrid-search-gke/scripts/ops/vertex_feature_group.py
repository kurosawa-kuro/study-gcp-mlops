"""Read a single property's online featureValues from a Vertex Feature Group.

Phase 5/6 wires `property_features_daily` into a Vertex AI Feature Group
(``infra/terraform/modules/vertex/main.tf``). This script verifies the
group is reachable and serving the latest day's row for one property.

Usage::

    PROPERTY_ID=p001 make ops-vertex-feature-group

Exit codes:
    0  — entity returned at least one feature value
    1  — config / not-found / IAM error
"""

from __future__ import annotations

import os

from scripts._common import env, fail


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("VERTEX_LOCATION", env("REGION", "asia-northeast1"))
    fg_id = env("VERTEX_FEATURE_GROUP_ID", "property_features")
    property_id = os.environ.get("PROPERTY_ID", "p001")
    if not project_id:
        return fail("vertex-feature-group: PROJECT_ID is required")

    try:
        from google.cloud.aiplatform_v1beta1 import (
            FeatureOnlineStoreServiceClient,
            FetchFeatureValuesRequest,
        )
    except ImportError:
        return fail("vertex-feature-group: google-cloud-aiplatform[v1beta1] required.")

    parent = (
        f"projects/{project_id}/locations/{region}/featureOnlineStores/"
        f"{env('VERTEX_FEATURE_ONLINE_STORE_ID', 'mlops_dev_feature_store')}/"
        f"featureViews/{fg_id}"
    )
    client = FeatureOnlineStoreServiceClient()
    req = FetchFeatureValuesRequest(
        feature_view=parent,
        data_key=FetchFeatureValuesRequest.DataKey(key=property_id),
    )
    try:
        resp = client.fetch_feature_values(request=req)
    except Exception as exc:
        return fail(f"vertex-feature-group: fetch failed: {exc}")

    kv = list(getattr(resp.key_values, "features", []) or [])
    if not kv:
        return fail(
            f"vertex-feature-group: empty feature set for property_id={property_id!r}. "
            f"Check that the daily sync job populated the group."
        )

    print(f"vertex-feature-group PASS: {len(kv)} feature(s) for property_id={property_id!r}")
    for fv in kv[:20]:
        print(f"  {getattr(fv, 'name', '-')} = {getattr(fv, 'value', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
