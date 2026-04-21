"""LightGBM 学習パイプライン（カリフォルニア住宅価格予測）."""

from pathlib import Path

import lightgbm as lgb
import pandas as pd

from common import MODEL_COLS, TARGET_COL, get_logger
from training.evaluation import evaluate, save_metrics

logger = get_logger(__name__)

LGB_PARAMS = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "verbosity": -1,
}
NUM_BOOST_ROUND = 300


def train(train_df: pd.DataFrame, test_df: pd.DataFrame, model_dir: str, run_id: str) -> dict:
    """学習を実行し、モデルを保存して評価指標を返す."""
    X_train = train_df[MODEL_COLS].values
    y_train = train_df[TARGET_COL].values
    X_test = test_df[MODEL_COLS].values
    y_test = test_df[TARGET_COL].values

    train_set = lgb.Dataset(X_train, label=y_train)
    valid_set = lgb.Dataset(X_test, label=y_test, reference=train_set)

    booster = lgb.train(
        LGB_PARAMS,
        train_set,
        num_boost_round=NUM_BOOST_ROUND,
        valid_sets=[valid_set],
        callbacks=[lgb.log_evaluation(period=50)],
    )

    # 評価
    y_pred = booster.predict(X_test)
    metrics = evaluate(y_test, y_pred)
    metrics["run_id"] = run_id

    # モデル保存: models/{run_id}/
    run_dir = Path(model_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(run_dir / "model.lgb"))
    save_metrics(metrics, str(run_dir / "metrics.json"))

    # latest シンボリックリンク更新（アトミック）
    latest = Path(model_dir) / "latest"
    latest_tmp = Path(model_dir) / f".latest_tmp_{run_id}"
    latest_tmp.symlink_to(run_id)
    latest_tmp.replace(latest)

    logger.info("Run ID:  %s", run_id)
    logger.info("Metrics: RMSE=%s, R²=%s", metrics["rmse"], metrics["r2"])
    logger.info("Model saved to %s", run_dir / "model.lgb")

    return metrics
