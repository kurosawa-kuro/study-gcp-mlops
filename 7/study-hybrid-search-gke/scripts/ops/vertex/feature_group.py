"""Fetch a single property's online featureValues from the Vertex Feature
Online Store.

Phase 7 (Run 2) added the Optimized FeatureOnlineStore via
``infra/terraform/modules/vertex/main.tf``. After ``terraform apply`` +
the first sync completes, the store auto-provisions a regional public
endpoint (``dedicatedServingEndpoint.publicEndpointDomainName``) of the
shape ``<NUMERIC>.<region>-<project_number>.featurestore.vertexai.goog``.
The Optimized type **only accepts requests on that endpoint**, not on
the global ``aiplatform.googleapis.com`` host — clients constructed
with the default endpoint fail with ``501 Operation is not implemented``.

This script:
1. Reads the FeatureOnlineStore resource to discover the public
   endpoint domain (so callers don't have to hardcode it).
2. Constructs ``FeatureOnlineStoreServiceClient`` against that endpoint.
3. Issues ``FetchFeatureValues`` for ``PROPERTY_ID``.

Usage::

    PROPERTY_ID=p001 make ops-vertex-feature-group

Exit codes:
    0  — entity returned at least one feature value
    1  — config error / endpoint not yet provisioned / IAM / not-found
"""

from __future__ import annotations

import os

from scripts._common import env, fail


def main() -> int:
    project_id = env("PROJECT_ID")
    region = env("VERTEX_LOCATION", env("REGION", "asia-northeast1"))
    online_store_id = env("VERTEX_FEATURE_ONLINE_STORE_ID", "mlops_dev_feature_store")
    feature_view_id = env("VERTEX_FEATURE_VIEW_ID", "property_features")
    property_id = os.environ.get("PROPERTY_ID", "p001")
    if not project_id:
        return fail("vertex-feature-group: PROJECT_ID is required")

    try:
        from google.cloud.aiplatform_v1beta1 import (
            FeatureOnlineStoreAdminServiceClient,
            FeatureOnlineStoreServiceClient,
            FeatureViewDataKey,
            FetchFeatureValuesRequest,
        )
    except ImportError:
        return fail("vertex-feature-group: google-cloud-aiplatform[v1beta1] required.")

    # 1. Discover the regional public endpoint via the Admin API.
    admin_endpoint = f"{region}-aiplatform.googleapis.com"
    admin = FeatureOnlineStoreAdminServiceClient(client_options={"api_endpoint": admin_endpoint})
    store_name = f"projects/{project_id}/locations/{region}/featureOnlineStores/{online_store_id}"
    try:
        store = admin.get_feature_online_store(name=store_name)
    except Exception as exc:
        return fail(f"vertex-feature-group: admin lookup failed: {exc}")

    endpoint = getattr(store, "dedicated_serving_endpoint", None)
    public_domain = (
        getattr(endpoint, "public_endpoint_domain_name", "") if endpoint is not None else ""
    )
    if not public_domain:
        return fail(
            "vertex-feature-group: dedicatedServingEndpoint.publicEndpointDomainName "
            "is empty — Optimized FeatureOnlineStore not yet provisioned. Wait 20-30 min "
            "after terraform apply + initial sync, then retry."
        )

    print(f"vertex-feature-group: public endpoint = {public_domain}")

    # 2. Construct the data-plane client against the regional public endpoint.
    serving = FeatureOnlineStoreServiceClient(client_options={"api_endpoint": public_domain})
    feature_view = (
        f"projects/{project_id}/locations/{region}/featureOnlineStores/"
        f"{online_store_id}/featureViews/{feature_view_id}"
    )
    req = FetchFeatureValuesRequest(
        feature_view=feature_view,
        data_key=FeatureViewDataKey(key=property_id),
    )
    try:
        resp = serving.fetch_feature_values(request=req)
    except Exception as exc:
        return fail(f"vertex-feature-group: fetch failed: {exc}")

    kv = list(getattr(resp.key_values, "features", []) or [])
    if not kv:
        return fail(
            f"vertex-feature-group: empty feature set for property_id={property_id!r}. "
            f"Check that the FeatureView sync ran (cron `0 * * * *`) and the entity exists."
        )

    print(f"vertex-feature-group PASS: {len(kv)} feature(s) for property_id={property_id!r}")
    for fv in kv[:20]:
        print(f"  {getattr(fv, 'name', '-')} = {getattr(fv, 'value', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
