"""API パッケージのテスト（推論エンドポイント）."""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def api_client(tmp_path, sample_df):
    """学習済みモデルを作成し、FastAPI TestClient を返す."""
    from pipeline.feature_engineering import engineer_features
    from pipeline.preprocess import preprocess
    from ml.trainer.train import train

    model_dir = str(tmp_path / "models")
    train_df = engineer_features(preprocess(sample_df.iloc[:80]))
    test_df = engineer_features(preprocess(sample_df.iloc[80:]))
    train(train_df, test_df, model_dir, "test_run")

    os.environ["MODEL_PATH"] = str(tmp_path / "models" / "latest" / "model.lgb")

    with TestClient(app) as client:
        yield client

    os.environ.pop("MODEL_PATH", None)


class TestHealthEndpoint:
    def test_health(self, api_client):
        res = api_client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


class TestPredictEndpoint:
    def test_predict_returns_price(self, api_client):
        payload = {
            "MedInc": 8.3,
            "HouseAge": 41,
            "AveRooms": 6.9,
            "AveBedrms": 1.0,
            "Population": 322,
            "AveOccup": 2.5,
            "Latitude": 37.88,
            "Longitude": -122.23,
        }
        res = api_client.post("/predict", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert "predicted_price" in body
        assert isinstance(body["predicted_price"], float)
