"""``POST /search`` — hybrid search + optional rerank + popularity scoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_request_id, get_search_service
from app.api.mappers import search_request_to_input, to_search_response
from app.schemas import SearchRequest, SearchResponse
from app.services.search_service import SearchService, SearchServiceUnavailable

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(
    req: SearchRequest,
    explain: bool = Query(False, description="Include TreeSHAP attributions per item"),
    lexical: str = Query("meili", description="Lexical backend: meili|agent_builder"),
    service: SearchService = Depends(get_search_service),
    request_id: str = Depends(get_request_id),
) -> SearchResponse | JSONResponse:
    try:
        output = service.search(
            request_id=request_id,
            input=search_request_to_input(req, explain=explain, lexical_backend=lexical),
        )
    except SearchServiceUnavailable as exc:
        return JSONResponse({"detail": str(exc)}, status_code=503)
    return to_search_response(output)
