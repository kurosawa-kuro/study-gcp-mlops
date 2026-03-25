from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import PredictRequest, _parse_gcs_path, app


class TestParseGCSPath:
    def test_valid_path(self):
        bucket, blob = _parse_gcs_path("gs://my-bucket/models/20260325/model.pkl")
        assert bucket == "my-bucket"
        assert blob == "models/20260325/model.pkl"

    def test_invalid_path(self):
        with pytest.raises(ValueError, match="無効なGCSパス"):
            _parse_gcs_path("not-a-gcs-path")


class TestPredictAPI:
    @pytest.fixture()
    def client(self):
        import main
        mock_model = MagicMock()
        mock_model.predict.return_value = [2.5]
        main._model = mock_model
        main._model_path = "gs://test-bucket/models/model.pkl"
        return TestClient(app, raise_server_exceptions=False)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model_path" in data

    def test_predict_success(self, client):
        resp = client.post("/predict", json={"features": [1.0] * 8})
        assert resp.status_code == 200
        data = resp.json()
        assert "prediction" in data
        assert data["prediction"] == 2.5
        assert "model_path" in data

    def test_predict_wrong_features(self, client):
        resp = client.post("/predict", json={"features": [1.0, 2.0]})
        assert resp.status_code == 422
        assert "8個" in resp.json()["detail"]

    def test_predict_no_model(self):
        import main
        main._model = None
        main._model_path = ""
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.post("/predict", json={"features": [1.0] * 8})
        assert resp.status_code == 503
