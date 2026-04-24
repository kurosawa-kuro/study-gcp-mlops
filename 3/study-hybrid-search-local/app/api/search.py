from fastapi import APIRouter, Depends, HTTPException
from httpx import HTTPError

from app.dependencies import get_search_properties_usecase
from app.schemas import SearchParams
from common.core.logging import RequestContextVar, get_logger
from common.ports.inbound.search_usecase import SearchQuery
from pipeline.batch_serving_job.application.search_properties import SearchPropertiesUseCase

logger = get_logger(__name__)
router = APIRouter()


@router.get("/search")
def search(
    params: SearchParams = Depends(),
    usecase: SearchPropertiesUseCase = Depends(get_search_properties_usecase),
) -> dict:
    request_id = RequestContextVar.get("request_id", "unknown")
    logger.info(
        "search_started",
        extra={
            "request_id": request_id,
            "user_id": params.user_id or "anonymous",
            "query": params.q,
            "city": params.city,
            "layout": params.layout,
            "limit": params.limit,
        },
    )

    query = SearchQuery(
        q=params.q,
        user_id=params.user_id,
        city=params.city,
        layout=params.layout,
        price_lte=params.price_lte,
        pet=params.pet,
        walk_min=params.walk_min,
        limit=params.limit,
        candidate_limit=params.candidate_limit,
    )

    try:
        response = usecase.execute(query)
    except HTTPError as exc:
        logger.error(
            "search_backend_error",
            extra={"request_id": request_id, "error": str(exc), "error_type": "HTTPError"},
        )
        raise HTTPException(status_code=502, detail="Search backend unavailable") from exc
    except TimeoutError as exc:
        logger.error(
            "search_timeout",
            extra={"request_id": request_id, "error": str(exc)},
        )
        raise HTTPException(status_code=504, detail="Search request timed out") from exc
    except Exception as exc:
        logger.error(
            "search_unexpected_error",
            extra={"request_id": request_id, "error": str(exc), "error_type": type(exc).__name__},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Search failed") from exc

    logger.info(
        "search_completed",
        extra={
            "request_id": request_id,
            "user_id": params.user_id or "anonymous",
            "result_count": response.get("count", 0),
        },
    )
    return response
