"""Pydantic schemas for developer-facing ops endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class DestroyCheckFindingResponse(BaseModel):
    label: str
    severity: str
    items: list[str]
    note: str = ""


class DestroyCheckSummaryResponse(BaseModel):
    ok: int
    warn: int
    fail: int
    error: int
    passed: bool


class DestroyCheckResponse(BaseModel):
    project_id: str
    region: str
    vertex_location: str
    summary: DestroyCheckSummaryResponse
    findings: list[DestroyCheckFindingResponse]
