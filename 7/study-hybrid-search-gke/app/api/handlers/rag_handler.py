"""``POST /rag`` — Phase 6 T6 hybrid search + Gemini summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_rag_service, get_request_id
from app.api.mappers import rag_request_to_search_input, to_rag_response
from app.schemas.rag import RagRequest, RagResponse
from app.services.rag_service import RagService
from app.services.search_service import SearchServiceUnavailable

router = APIRouter()


@router.post("/rag", response_model=RagResponse)
def rag(
    req: RagRequest,
    service: RagService = Depends(get_rag_service),
    request_id: str = Depends(get_request_id),
) -> RagResponse | JSONResponse:
    try:
        output = service.summarize(
            request_id=request_id,
            input=rag_request_to_search_input(req),
            summary_top_n=req.summary_top_n,
        )
    except SearchServiceUnavailable as exc:
        return JSONResponse({"detail": str(exc)}, status_code=503)
    return to_rag_response(output)
