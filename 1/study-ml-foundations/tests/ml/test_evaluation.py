"""evaluation パッケージのテスト（指標算出・保存・W&B）."""

from pathlib import Path

import numpy as np

from ml.evaluation.metrics import evaluate, r2_score, rmse, save_metrics
from ml.evaluation.tracking import init_wandb, log_metrics


class TestMetrics:
    def test_rmse_perfect(self):
        y = np.array([1.0, 2.0, 3.0])
        assert rmse(y, y) == 0.0

    def test_rmse_known_value(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.0, 2.0, 4.0])
        # sqrt(mean([0, 0, 1])) = sqrt(1/3)
        expected = float(np.sqrt(1.0 / 3.0))
        assert abs(rmse(y_true, y_pred) - expected) < 1e-10

    def test_r2_perfect(self):
        y = np.array([1.0, 2.0, 3.0])
        assert r2_score(y, y) == 1.0

    def test_r2_constant_target_perfect(self):
        y = np.array([5.0, 5.0, 5.0])
        assert r2_score(y, y) == 0.0

    def test_r2_constant_target_with_error(self):
        y_true = np.array([5.0, 5.0, 5.0])
        y_pred = np.array([4.0, 5.0, 6.0])
        assert np.isnan(r2_score(y_true, y_pred))

    def test_evaluate_returns_keys(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.1, 2.1, 2.9])
        result = evaluate(y_true, y_pred)
        assert "rmse" in result
        assert "r2" in result


class TestSaveMetrics:
    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "metrics.json")
        save_metrics({"rmse": 0.5, "r2": 0.8}, path)
        assert Path(path).exists()


class TestTracking:
    def test_wandb_offline(self):
        init_wandb(api_key="", project="test-project")
        log_metrics({"rmse": 0.5})
