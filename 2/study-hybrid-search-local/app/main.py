from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.middleware import RequestContextMiddleware, global_exception_handler
from app.api.feedback import router as feedback_router
from app.api.search import router as search_router
from common.core.logging import RequestContextVar, get_logger, setup_logging

# Initialize logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Real Estate Search API", version="0.1.0")

# Add request context middleware (must be first)
app.add_middleware(RequestContextMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return await global_exception_handler(request, exc)


# Validation error handler for Pydantic validation failures
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = RequestContextVar.get("request_id", "unknown")
    logger.warning(
        "Validation error",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "errors": exc.errors(),
        },
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "ValidationError",
                "message": "Request validation failed",
                "request_id": request_id,
                "details": exc.errors(),
            }
        },
    )


app.include_router(search_router)
app.include_router(feedback_router)

logger.info("Application started", extra={"version": "0.1.0"})
