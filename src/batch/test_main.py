import json
import pickle
import tempfile
from unittest.mock import MagicMock, patch

import mlflow
import mlflow.sklearn
import pytest

from dataset import load_data
from main import upload_log
from model_store import load_local, save_local
from train import build_model, evaluate, train


class TestDataset:
    def test_load_data_shapes(self):
        X_train, X_test, y_train, y_test = load_data()

        assert len(X_train) > 0
        assert len(X_test) > 0
        assert len(X_train) == len(y_train)
        assert len(X_test) == len(y_test)
        assert X_train.shape[1] == 8

    def test_load_data_split_ratio(self):
        X_train, X_test, _, _ = load_data(test_size=0.3)
        total = len(X_train) + len(X_test)
        assert abs(len(X_test) / total - 0.3) < 0.01


class TestTrain:
    @pytest.fixture()
    def trained_model(self):
        X_train, X_test, y_train, y_test = load_data()
        model = build_model(n_estimators=10, max_depth=5)
        train(model, X_train, y_train)
        return model, X_test, y_test

    def test_build_model(self):
        model = build_model(n_estimators=50, max_depth=8)
        assert model.n_estimators == 50
        assert model.max_depth == 8

    def test_train_and_evaluate(self, trained_model):
        model, X_test, y_test = trained_model
        metrics = evaluate(model, X_test, y_test)

        assert "rmse" in metrics
        assert "mae" in metrics
        assert metrics["rmse"] > 0
        assert metrics["mae"] > 0
        assert metrics["rmse"] < 1.0

    def test_feature_importances(self, trained_model):
        model, _, _ = trained_model
        importances = model.feature_importances_
        assert len(importances) == 8
        assert abs(sum(importances) - 1.0) < 1e-6


class TestModelStore:
    def test_save_and_load_local(self):
        X_train, _, y_train, _ = load_data()
        model = build_model(n_estimators=10, max_depth=5)
        train(model, X_train, y_train)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name

        save_local(model, path)
        loaded = load_local(path)

        assert loaded.n_estimators == model.n_estimators
        pred_orig = model.predict(X_train[:5])
        pred_loaded = loaded.predict(X_train[:5])
        assert list(pred_orig) == list(pred_loaded)

    @patch("model_store._get_storage_client")
    def test_save_gcs(self, mock_get_client):
        from model_store import save_gcs

        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_get_client.return_value.bucket.return_value = mock_bucket

        model = build_model(n_estimators=10)
        result = save_gcs(model, "test-bucket")

        assert result.startswith("gs://test-bucket/models/")
        assert result.endswith(".pkl")
        mock_blob.upload_from_file.assert_called_once()


class TestUploadLog:
    @patch("main.storage.Client")
    def test_upload_log_creates_correct_path(self, mock_client_cls):
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client_cls.return_value.bucket.return_value = mock_bucket

        log_data = {"job": "ml-batch", "status": "success"}
        path = upload_log("test-bucket", "ml-batch", log_data)

        assert path.startswith("logs/")
        assert "ml-batch_" in path
        assert path.endswith(".json")

    @patch("main.storage.Client")
    def test_upload_log_sends_json(self, mock_client_cls):
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client_cls.return_value.bucket.return_value = mock_bucket

        log_data = {"job": "ml-batch", "status": "success"}
        upload_log("test-bucket", "ml-batch", log_data)

        call_args = mock_blob.upload_from_string.call_args
        uploaded = json.loads(call_args[0][0])
        assert uploaded["job"] == "ml-batch"
        assert uploaded["status"] == "success"
        assert call_args[1]["content_type"] == "application/json"


class TestMLflowIntegration:
    def test_mlflow_tracking(self, tmp_path):
        tracking_uri = f"file://{tmp_path / 'mlruns'}"
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("test-experiment")

        with mlflow.start_run() as run:
            X_train, X_test, y_train, y_test = load_data()
            model = build_model(n_estimators=10, max_depth=5)
            train(model, X_train, y_train)
            metrics = evaluate(model, X_test, y_test)

            mlflow.log_params({
                "n_estimators": 10,
                "max_depth": 5,
                "random_state": 42,
                "test_size": 0.2,
            })
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(model, artifact_path="model")

        client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
        run_data = client.get_run(run.info.run_id)

        assert run_data.data.params["n_estimators"] == "10"
        assert run_data.data.params["max_depth"] == "5"
        assert float(run_data.data.metrics["rmse"]) > 0
        assert float(run_data.data.metrics["mae"]) > 0

    def test_mlflow_model_loadable(self, tmp_path):
        tracking_uri = f"file://{tmp_path / 'mlruns'}"
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("test-model-load")

        X_train, X_test, y_train, y_test = load_data()
        model = build_model(n_estimators=10, max_depth=5)
        train(model, X_train, y_train)

        with mlflow.start_run() as run:
            mlflow.sklearn.log_model(model, artifact_path="model")

        model_uri = f"runs:/{run.info.run_id}/model"
        loaded_model = mlflow.sklearn.load_model(model_uri)
        preds = loaded_model.predict(X_test[:5])
        assert len(preds) == 5


class TestBQStore:
    @patch("bq_store._get_bq_client")
    def test_insert_metrics(self, mock_get_client, monkeypatch):
        from bq_store import insert_metrics

        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []
        mock_get_client.return_value = mock_client

        monkeypatch.setenv("BQ_DATASET", "mlops")
        monkeypatch.setenv("GCP_PROJECT", "mlops-dev-a")

        row = {
            "run_id": "test-run-123",
            "timestamp": "2026-03-26T00:00:00+00:00",
            "rmse": 0.54,
            "mae": 0.37,
            "model_path": "gs://bucket/models/model.pkl",
            "n_estimators": 100,
            "max_depth": 10,
        }
        insert_metrics(row)

        mock_client.insert_rows_json.assert_called_once()
        call_args = mock_client.insert_rows_json.call_args
        assert call_args[0][0] == "mlops-dev-a.mlops.metrics"
        assert call_args[0][1][0]["run_id"] == "test-run-123"

    @patch("bq_store._get_bq_client")
    def test_insert_metrics_error(self, mock_get_client):
        from bq_store import insert_metrics

        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = [{"errors": "something"}]
        mock_get_client.return_value = mock_client

        with pytest.raises(RuntimeError, match="BigQuery insert"):
            insert_metrics({"run_id": "x", "timestamp": "t", "rmse": 0.5, "mae": 0.3})
