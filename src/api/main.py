import io
import os
import pickle
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_model = None
_model_path = ""


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _model, _model_path
    _model, _model_path = load_best_model()
    print(f"モデルロード完了: {_model_path}")
    yield


app = FastAPI(title="ML Predict API", lifespan=lifespan)


class PredictRequest(BaseModel):
    features: list[float]


class PredictResponse(BaseModel):
    prediction: float
    model_path: str


def _parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    m = re.match(r"gs://([^/]+)/(.+)", gcs_path)
    if not m:
        raise ValueError(f"無効なGCSパス: {gcs_path}")
    return m.group(1), m.group(2)


def load_best_model() -> tuple[object, str]:
    """BigQueryから最良モデルのパスを取得し、GCSからロードする。"""
    from google.cloud import bigquery, storage

    project = os.environ.get("GCP_PROJECT", "mlops-dev-a")
    dataset = os.environ.get("BQ_DATASET", "mlops")

    bq = bigquery.Client()
    query = f"""
    SELECT model_path
    FROM `{project}.{dataset}.metrics`
    ORDER BY rmse ASC
    LIMIT 1
    """
    rows = list(bq.query(query).result())
    if not rows:
        raise RuntimeError("BigQueryにメトリクスが存在しません")

    model_path = rows[0].model_path
    bucket_name, blob_name = _parse_gcs_path(model_path)

    gcs = storage.Client()
    blob = gcs.bucket(bucket_name).blob(blob_name)
    buf = io.BytesIO()
    blob.download_to_file(buf)
    buf.seek(0)
    model = pickle.load(buf)  # noqa: S301

    return model, model_path


@app.get("/health")
def health():
    return {"status": "ok", "model_path": _model_path}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="モデル未ロード")
    if len(req.features) != 8:
        raise HTTPException(status_code=422, detail="特徴量は8個必要です（California Housing）")

    prediction = _model.predict([req.features])
    return PredictResponse(
        prediction=float(prediction[0]),
        model_path=_model_path,
    )
