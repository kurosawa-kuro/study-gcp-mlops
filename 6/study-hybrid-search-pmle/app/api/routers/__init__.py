"""HTTP routers — one APIRouter per concern."""

from .feedback_router import router as feedback_router
from .health_router import router as health_router
from .model_router import router as model_router
from .retrain_router import router as retrain_router
from .search_router import router as search_router
from .ui_router import build_ui_router

__all__ = [
    "build_ui_router",
    "feedback_router",
    "health_router",
    "model_router",
    "retrain_router",
    "search_router",
]
