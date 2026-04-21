from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_record_feedback_usecase
from app.schemas import FeedbackRequest
from common.core.logging import RequestContextVar, get_logger
from common.ports.inbound.feedback_usecase import FeedbackCommand
from pipeline.application.record_feedback import RecordFeedbackUseCase

logger = get_logger(__name__)
router = APIRouter()


@router.post("/feedback")
def feedback(
    payload: FeedbackRequest,
    usecase: RecordFeedbackUseCase = Depends(get_record_feedback_usecase),
) -> dict[str, object]:
    request_id = RequestContextVar.get("request_id", "unknown")
    logger.info(
        "feedback_started",
        extra={
            "request_id": request_id,
            "user_id": payload.user_id or "anonymous",
            "property_id": payload.property_id,
            "action": payload.action,
            "search_log_id": payload.search_log_id,
        },
    )

    try:
        command = FeedbackCommand(
            user_id=payload.user_id,
            property_id=payload.property_id,
            action=payload.action,
            search_log_id=payload.search_log_id,
        )
        response = usecase.execute(command)
        updated_search_log = bool(response.get("search_log_updated", False))
    except LookupError as exc:
        logger.warning(
            "feedback_search_log_not_found",
            extra={
                "request_id": request_id,
                "user_id": payload.user_id or "anonymous",
                "search_log_id": payload.search_log_id,
            },
        )
        raise HTTPException(status_code=404, detail="search_log_id not found") from exc
    except Exception as exc:
        logger.error(
            "feedback_error",
            extra={
                "request_id": request_id,
                "user_id": payload.user_id or "anonymous",
                "property_id": payload.property_id,
                "action": payload.action,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Feedback processing failed") from exc

    logger.info(
        "feedback_completed",
        extra={
            "request_id": request_id,
            "user_id": payload.user_id or "anonymous",
            "property_id": payload.property_id,
            "action": payload.action,
            "search_log_updated": updated_search_log,
        },
    )

    return response
