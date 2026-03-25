import json
import os
from datetime import datetime, timezone

import mlflow
import mlflow.sklearn

from dataset import load_data
from model_store import save_gcs, save_local
from train import build_model, evaluate, train

N_ESTIMATORS = int(os.environ.get("N_ESTIMATORS", "100"))
MAX_DEPTH = int(os.environ.get("MAX_DEPTH", "10"))
RANDOM_STATE = int(os.environ.get("RANDOM_STATE", "42"))
TEST_SIZE = float(os.environ.get("TEST_SIZE", "0.2"))


def main():
    print("=== ML学習パイプライン開始 ===")

    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "california-housing")
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run():
        # 1. データ取得
        print("データ取得中...")
        X_train, X_test, y_train, y_test = load_data(
            test_size=TEST_SIZE, random_state=RANDOM_STATE
        )
        print(f"  train: {len(X_train)}件, test: {len(X_test)}件")

        # 2. パラメータ記録
        mlflow.log_params({
            "n_estimators": N_ESTIMATORS,
            "max_depth": MAX_DEPTH,
            "random_state": RANDOM_STATE,
            "test_size": TEST_SIZE,
        })

        # 3. 学習
        print("モデル学習中...")
        model = build_model(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
        )
        train(model, X_train, y_train)

        # 4. 評価 & メトリクス記録
        metrics = evaluate(model, X_test, y_test)
        mlflow.log_metrics(metrics)
        print(f"  RMSE: {metrics['rmse']:.4f}")
        print(f"  MAE:  {metrics['mae']:.4f}")

        # 5. MLflowにモデル記録
        mlflow.sklearn.log_model(model, artifact_path="model")

        # 6. GCS保存（設定時）
        bucket_name = os.environ.get("GCS_BUCKET")
        if bucket_name:
            gcs_path = save_gcs(model, bucket_name)
            mlflow.log_param("model_gcs_path", gcs_path)
            print(f"モデル保存完了: {gcs_path}")
        else:
            local_path = save_local(model, "outputs/model.pkl")
            print(f"GCS_BUCKET未設定のためローカル保存: {local_path}")

        # 7. ログ出力
        log = {
            "job": "ml-train",
            "status": "success",
            "metrics": metrics,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "mlflow_run_id": mlflow.active_run().info.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(log, ensure_ascii=False, indent=2))

    print("=== ML学習パイプライン完了 ===")


if __name__ == "__main__":
    main()
