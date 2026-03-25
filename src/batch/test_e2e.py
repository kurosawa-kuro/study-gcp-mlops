"""エンドツーエンドテスト: 学習→評価→モデル保存→BQ投入→API推論の一周を検証。"""
import io
import pickle
from unittest.mock import MagicMock, patch

import mlflow

from dataset import load_data
from model_store import save_local
from train import build_model, evaluate, train


class TestE2EPipeline:
    def test_train_to_predict(self, tmp_path):
        """学習→評価→ローカル保存→モデルロード→推論の一周を検証。"""
        # 1. データ取得・学習・評価
        X_train, X_test, y_train, y_test = load_data()
        model = build_model(n_estimators=10, max_depth=5)
        train(model, X_train, y_train)
        metrics = evaluate(model, X_test, y_test)

        assert metrics["rmse"] > 0
        assert metrics["mae"] > 0

        # 2. モデル保存・読み込み
        model_path = str(tmp_path / "model.pkl")
        save_local(model, model_path)

        with open(model_path, "rb") as f:
            loaded_model = pickle.load(f)  # noqa: S301

        # 3. 推論検証（APIと同じフロー）
        sample = X_test.iloc[0].tolist()
        pred_orig = model.predict([sample])[0]
        pred_loaded = loaded_model.predict([sample])[0]

        assert pred_orig == pred_loaded
        assert isinstance(pred_orig, float)

    @patch("bq_store._get_bq_client")
    @patch("model_store._get_storage_client")
    def test_gcs_save_and_bq_insert(self, mock_gcs_client, mock_bq_client, tmp_path):
        """GCS保存→BQ投入が正しく呼ばれることを検証。"""
        from bq_store import insert_metrics
        from model_store import save_gcs

        # GCS mock
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_client.return_value.bucket.return_value = mock_bucket

        # BQ mock
        mock_bq = MagicMock()
        mock_bq.insert_rows_json.return_value = []
        mock_bq_client.return_value = mock_bq

        # 学習
        X_train, X_test, y_train, y_test = load_data()
        model = build_model(n_estimators=10, max_depth=5)
        train(model, X_train, y_train)
        metrics = evaluate(model, X_test, y_test)

        # GCS保存
        gcs_path = save_gcs(model, "test-bucket")
        assert gcs_path.startswith("gs://test-bucket/models/")
        mock_blob.upload_from_file.assert_called_once()

        # BQ投入
        bq_row = {
            "run_id": "test-run",
            "timestamp": "2026-03-26T00:00:00+00:00",
            "rmse": metrics["rmse"],
            "mae": metrics["mae"],
            "model_path": gcs_path,
            "n_estimators": 10,
            "max_depth": 5,
        }
        insert_metrics(bq_row)
        mock_bq.insert_rows_json.assert_called_once()

        # 投入されたデータの検証
        call_args = mock_bq.insert_rows_json.call_args
        inserted_row = call_args[0][1][0]
        assert inserted_row["rmse"] == metrics["rmse"]
        assert inserted_row["model_path"] == gcs_path

    def test_mlflow_to_evaluation(self, tmp_path):
        """MLflow記録→メトリクス取得→最良モデル選択の流れを検証。"""
        tracking_uri = f"file://{tmp_path / 'mlruns'}"
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("e2e-test")

        X_train, X_test, y_train, y_test = load_data()

        # 2つのモデルを学習（精度の違い）
        runs = []
        for depth in [3, 10]:
            model = build_model(n_estimators=10, max_depth=depth)
            train(model, X_train, y_train)
            metrics = evaluate(model, X_test, y_test)

            with mlflow.start_run() as run:
                mlflow.log_params({"max_depth": depth})
                mlflow.log_metrics(metrics)
                runs.append({"run_id": run.info.run_id, "rmse": metrics["rmse"], "max_depth": depth})

        # 最良モデル選択（BigQueryのSQLと同じロジック）
        best = min(runs, key=lambda r: r["rmse"])
        assert best["max_depth"] == 10  # deeper tree = better RMSE

        # MLflowから検証
        client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
        best_run = client.get_run(best["run_id"])
        assert float(best_run.data.metrics["rmse"]) == best["rmse"]
