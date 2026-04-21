"""FastAPI 推論エンドポイント."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import lightgbm as lgb
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import Settings
from common import FEATURE_COLS, MODEL_COLS, TARGET_COL, get_logger
from pipelines.housing_prices import Settings as PipelineSettings
from pipelines.housing_prices import get_repository
from pipelines.housing_prices.feature_engineering import engineer_features_input
from pipelines.housing_prices.preprocess import preprocess_input

logger = get_logger(__name__)

# フロントエンド用デフォルト値
_DEFAULTS = {
    "MedInc": 8.3, "HouseAge": 41, "AveRooms": 6.9, "AveBedrms": 1.0,
    "Population": 322, "AveOccup": 2.5, "Latitude": 37.88, "Longitude": -122.23,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時にモデルをロードし、app.state に格納する."""
    settings = Settings()
    model_path = settings.model_path
    try:
        app.state.booster = lgb.Booster(model_file=model_path)
        logger.info("Model loaded from %s", model_path)
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {model_path}: {e}") from e
    yield


app = FastAPI(lifespan=lifespan)
_api_root = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(_api_root / "static")), name="static")
templates = Jinja2Templates(directory=str(_api_root / "templates"))


class PredictRequest(BaseModel):
    MedInc: float
    HouseAge: float
    AveRooms: float
    AveBedrms: float
    Population: float
    AveOccup: float
    Latitude: float
    Longitude: float


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"feature_cols": FEATURE_COLS, "defaults": _DEFAULTS, "active": "predict"},
    )


@app.post("/predict")
def predict(request: Request, req: PredictRequest):
    booster = request.app.state.booster
    values = preprocess_input(req.model_dump())
    values = engineer_features_input(values)
    features = np.array([[values[col] for col in MODEL_COLS]])
    prediction = booster.predict(features)[0]
    return {"predicted_price": round(float(prediction), 4)}


@app.get("/metrics", response_class=HTMLResponse)
def metrics_page(request: Request):
    settings = Settings()
    metrics_path = Path(settings.model_path).parent / "metrics.json"
    try:
        metrics = json.loads(metrics_path.read_text())
    except FileNotFoundError:
        metrics = None
    return templates.TemplateResponse(
        request, "metrics.html", {"metrics": metrics, "active": "metrics"}
    )


@app.get("/data", response_class=HTMLResponse)
def data_page(request: Request, split: str = "train", limit: int = 50):
    split = split if split in ("train", "test") else "train"
    limit = max(1, min(limit, 500))
    try:
        repo = get_repository(PipelineSettings())
        df = repo.fetch_train() if split == "train" else repo.fetch_test()
        total = len(df)
        sample = df.head(limit)
        columns = list(sample.columns)
        rows = sample.to_dict(orient="records")
    except Exception as e:
        logger.warning("Failed to load data: %s", e)
        columns, rows, total = [], [], 0
    return templates.TemplateResponse(
        request,
        "data.html",
        {
            "active": "data",
            "split": split,
            "limit": limit,
            "total": total,
            "columns": columns,
            "rows": rows,
            "target": TARGET_COL,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}
