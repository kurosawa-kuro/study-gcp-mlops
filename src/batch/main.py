import json
import logging
import os
import sys
from datetime import datetime, timezone

import mlflow
import mlflow.sklearn
from google.cloud import storage

from bq_store import insert_metrics
from dataset import load_data
from model_store import save_gcs, save_local
from train import build_model, evaluate, train

logger = logging.getLogger("ml-batch")
logging.basicConfig(
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s","timestamp":"%(asctime)s"}',
)

N_ESTIMATORS = int(os.environ.get("N_ESTIMATORS", "100"))
MAX_DEPTH = int(os.environ.get("MAX_DEPTH", "10"))
RANDOM_STATE = int(os.environ.get("RANDOM_STATE", "42"))
TEST_SIZE = float(os.environ.get("TEST_SIZE", "0.2"))


def upload_log(bucket_name: str, job_name: str, log_data: dict) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    now = datetime.now(timezone.utc)
    path = f"logs/{now.strftime('%Y%m%d')}/{job_name}_{now.strftime('%Y%m%d_%H%M%S')}.json"

    blob = bucket.blob(path)
    blob.upload_from_string(json.dumps(log_data, ensure_ascii=False), content_type="application/json")

    return path


def main():
    job_name = os.environ.get("JOB_NAME", "ml-batch")
    logger.info(f"ML学習パイプライン開始: {job_name}")

    try:
        experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "california-housing")
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run():
            # 1. データ取得
            logger.info("データ取得中...")
            X_train, X_test, y_train, y_test = load_data(
                test_size=TEST_SIZE, random_state=RANDOM_STATE
            )
            logger.info(f"train: {len(X_train)}件, test: {len(X_test)}件")

            # 2. パラメータ記録
            mlflow.log_params({
                "n_estimators": N_ESTIMATORS,
                "max_depth": MAX_DEPTH,
                "random_state": RANDOM_STATE,
                "test_size": TEST_SIZE,
            })

            # 3. 学習
            logger.info("モデル学習中...")
            model = build_model(
                n_estimators=N_ESTIMATORS,
                max_depth=MAX_DEPTH,
                random_state=RANDOM_STATE,
            )
            train(model, X_train, y_train)

            # 4. 評価 & メトリクス記録
            metrics = evaluate(model, X_test, y_test)
            mlflow.log_metrics(metrics)
            logger.info(f"RMSE: {metrics['rmse']:.4f}, MAE: {metrics['mae']:.4f}")

            # 5. MLflowにモデル記録
            mlflow.sklearn.log_model(model, artifact_path="model")

            # 6. GCS保存（設定時）
            bucket_name = os.environ.get("GCS_BUCKET")
            if bucket_name:
                gcs_path = save_gcs(model, bucket_name)
                mlflow.log_param("model_gcs_path", gcs_path)
                logger.info(f"モデル保存完了: {gcs_path}")

                # 7. GCSにログ書き出し
                log_data = {
                    "job": job_name,
                    "status": "success",
                    "metrics": metrics,
                    "train_size": len(X_train),
                    "test_size": len(X_test),
                    "mlflow_run_id": mlflow.active_run().info.run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                log_path = upload_log(bucket_name, job_name, log_data)
                logger.info(f"ログ書き出し完了: gs://{bucket_name}/{log_path}")

                # 8. BigQueryにメトリクス投入
                if os.environ.get("BQ_DATASET"):
                    bq_row = {
                        "run_id": mlflow.active_run().info.run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "rmse": metrics["rmse"],
                        "mae": metrics["mae"],
                        "model_path": gcs_path,
                        "n_estimators": N_ESTIMATORS,
                        "max_depth": MAX_DEPTH,
                    }
                    insert_metrics(bq_row)
                    logger.info("BigQueryメトリクス投入完了")
                else:
                    logger.info("BQ_DATASET未設定のためBigQuery投入スキップ")
            else:
                local_path = save_local(model, "outputs/model.pkl")
                logger.info(f"GCS_BUCKET未設定のためローカル保存: {local_path}")

        logger.info("ML学習パイプライン完了")

    except Exception as e:
        logger.error(f"ML学習パイプライン失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
