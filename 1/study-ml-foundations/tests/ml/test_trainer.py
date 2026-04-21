"""trainer パッケージのテスト（LightGBM 学習）."""

from pathlib import Path

from ml.pipeline.feature_engineering import engineer_features
from ml.pipeline.preprocess import preprocess
from ml.trainer.train import train


class TestTrain:
    def test_train_saves_model_and_metrics(self, sample_df, tmp_path):
        train_df = engineer_features(preprocess(sample_df.iloc[:80]))
        test_df = engineer_features(preprocess(sample_df.iloc[80:]))
        model_dir = str(tmp_path / "models")
        run_id = "test_run_001"

        metrics = train(train_df, test_df, model_dir, run_id)

        assert "rmse" in metrics
        assert "r2" in metrics
        assert "run_id" in metrics
        assert metrics["run_id"] == run_id
        assert metrics["rmse"] > 0
        assert Path(model_dir, run_id, "model.lgb").exists()
        assert Path(model_dir, run_id, "metrics.json").exists()
        assert Path(model_dir, "latest").is_symlink()
