import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.middleware import RequestContextMiddleware, global_exception_handler
from app.api.feedback import router as feedback_router
from app.api.search import router as search_router
from common.core.logging import RequestContextVar, get_logger, setup_logging

# Initialize logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Real Estate Search API", version="0.1.0")
_APP_ROOT = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(_APP_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(_APP_ROOT / "templates"))

# Add request context middleware (must be first)
app.add_middleware(RequestContextMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    # Phase 4/5 alignment: expose a readiness alias with the same healthy payload.
    return {"status": "ok"}


@app.get("/")
def home(request: Request):
    search_defaults = {
        "q": "渋谷 1LDK",
        "city": "渋谷区",
        "layout": "1LDK",
        "price_lte": 200000,
        "walk_min": 10,
        "limit": 20,
        "candidate_limit": 100,
    }
    feedback_defaults = {
        "user_id": 1,
        "property_id": 1001,
        "action": "click",
        "search_log_id": 1,
    }
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "active": "predict",
            "search_defaults": search_defaults,
            "feedback_defaults": feedback_defaults,
        },
    )


@app.get("/metrics")
def metrics_page(request: Request):
    payload = {
        "service": "phase2-local-api",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pythonpath": os.getenv("PYTHONPATH", ""),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }
    return templates.TemplateResponse(
        request,
        "metrics.html",
        {"active": "metrics", "metrics": payload},
    )


@app.get("/data")
def data_page(request: Request):
    rows = [
        {
            "endpoint": "GET /search",
            "summary": "Hybrid property search",
            "example": "q=渋谷 1LDK&limit=20",
        },
        {
            "endpoint": "POST /feedback",
            "summary": "Record click/favorite/inquiry signal",
            "example": '{"property_id":1001,"action":"click"}',
        },
    ]
    return templates.TemplateResponse(
        request,
        "data.html",
        {
            "active": "data",
            "columns": ["endpoint", "summary", "example"],
            "rows": rows,
            "total": len(rows),
        },
    )


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
