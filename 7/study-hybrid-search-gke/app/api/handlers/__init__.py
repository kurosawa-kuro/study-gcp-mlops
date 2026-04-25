"""HTTP handler routers — one APIRouter per concern.

Phase D-2 split the single 699-line ``app/main.py`` ``create_app()`` into
focused routers. ``app/main.py`` now only registers these routers via
``include_router``.

Each handler is < 40 lines (Phase D-2 success criterion). Business logic
lives in ``app/services/``; mapping lives in ``app/api/mappers/``;
handlers only handle HTTP concerns (status codes, content negotiation).
"""

from .feedback_handler import router as feedback_router
from .health_handler import router as health_router
from .rag_handler import router as rag_router
from .retrain_handler import router as retrain_router
from .search_handler import router as search_router
from .ui_handler import build_ui_router

__all__ = [
    "build_ui_router",
    "feedback_router",
    "health_router",
    "rag_router",
    "retrain_router",
    "search_router",
]
