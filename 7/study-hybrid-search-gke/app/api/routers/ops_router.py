"""Developer-facing ops APIs."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.ops import (
    DestroyCheckFindingResponse,
    DestroyCheckResponse,
    DestroyCheckSummaryResponse,
)
from scripts._common import env
from scripts.ops.destroy_check import collect_findings

router = APIRouter(prefix="/ops")


@router.get("/destroy-check", response_model=DestroyCheckResponse)
def destroy_check(
    project_id: str = Query(default=env("PROJECT_ID", "mlops-dev-a")),
    region: str = Query(default=env("REGION", "asia-northeast1")),
    vertex_location: str = Query(default=env("VERTEX_LOCATION", env("REGION", "asia-northeast1"))),
) -> DestroyCheckResponse:
    findings = collect_findings(
        project_id=project_id,
        region=region,
        vertex_location=vertex_location,
    )
    ok = sum(1 for finding in findings if finding.severity == "OK")
    warn = sum(1 for finding in findings if finding.severity == "WARN")
    fail = sum(1 for finding in findings if finding.severity == "FAIL")
    error = sum(1 for finding in findings if finding.severity == "ERROR")
    return DestroyCheckResponse(
        project_id=project_id,
        region=region,
        vertex_location=vertex_location,
        summary=DestroyCheckSummaryResponse(
            ok=ok,
            warn=warn,
            fail=fail,
            error=error,
            passed=(fail == 0 and error == 0),
        ),
        findings=[
            DestroyCheckFindingResponse(
                label=finding.label,
                severity=finding.severity,
                items=list(finding.items),
                note=finding.note,
            )
            for finding in findings
        ],
    )
