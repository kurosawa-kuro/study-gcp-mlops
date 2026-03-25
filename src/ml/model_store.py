import io
import os
import pickle
from datetime import datetime, timezone

from sklearn.ensemble import RandomForestRegressor


def save_local(model: RandomForestRegressor, path: str) -> str:
    """モデルをローカルファイルに保存する。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    return path


def load_local(path: str) -> RandomForestRegressor:
    """ローカルファイルからモデルを読み込む。"""
    with open(path, "rb") as f:
        return pickle.load(f)  # noqa: S301


def _get_storage_client():
    from google.cloud import storage
    return storage.Client()


def save_gcs(model: RandomForestRegressor, bucket_name: str, prefix: str = "models") -> str:
    """モデルをGCSに保存する。返り値はGCSパス。"""

    buf = io.BytesIO()
    pickle.dump(model, buf)
    buf.seek(0)

    now = datetime.now(timezone.utc)
    blob_path = f"{prefix}/{now.strftime('%Y%m%d')}/model_{now.strftime('%Y%m%d_%H%M%S')}.pkl"

    client = _get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_file(buf, content_type="application/octet-stream")

    return f"gs://{bucket_name}/{blob_path}"


def load_gcs(bucket_name: str, blob_path: str) -> RandomForestRegressor:
    """GCSからモデルを読み込む。"""
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    buf = io.BytesIO()
    blob.download_to_file(buf)
    buf.seek(0)
    return pickle.load(buf)  # noqa: S301
