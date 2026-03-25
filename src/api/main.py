import io
import logging
import os
import pickle
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("ml-api")
logging.basicConfig(
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s","timestamp":"%(asctime)s"}',
)

_model = None
_model_path = ""


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _model, _model_path
    try:
        _model, _model_path = load_best_model()
        logger.info(f"モデルロード完了: {_model_path}")
    except Exception as e:
        logger.error(f"モデルロード失敗（APIは起動するが推論不可）: {e}")
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


def load_best_model(max_retries: int = 3) -> tuple[object, str]:
    """BigQueryから最良モデルのパスを取得し、GCSからロードする。リトライ付き。"""
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

    for attempt in range(max_retries):
        try:
            rows = list(bq.query(query).result())
            if not rows:
                raise RuntimeError("BigQueryにメトリクスが存在しません")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"BigQuery クエリ リトライ ({attempt + 1}/{max_retries}), {wait}秒待機: {e}")
                time.sleep(wait)
            else:
                raise

    model_path = rows[0].model_path
    bucket_name, blob_name = _parse_gcs_path(model_path)

    gcs = storage.Client()
    blob = gcs.bucket(bucket_name).blob(blob_name)

    for attempt in range(max_retries):
        try:
            buf = io.BytesIO()
            blob.download_to_file(buf)
            buf.seek(0)
            model = pickle.load(buf)  # noqa: S301
            return model, model_path
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"GCS ダウンロード リトライ ({attempt + 1}/{max_retries}), {wait}秒待機: {e}")
                time.sleep(wait)
            else:
                raise


@app.get("/health")
def health():
    status = "ok" if _model is not None else "degraded"
    return {"status": status, "model_path": _model_path}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="モデル未ロード。/health で状態を確認してください")
    if len(req.features) != 8:
        raise HTTPException(status_code=422, detail="特徴量は8個必要です（California Housing）")

    prediction = _model.predict([req.features])
    return PredictResponse(
        prediction=float(prediction[0]),
        model_path=_model_path,
    )
