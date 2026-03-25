import json
import os
from datetime import datetime, timezone

from google.cloud import storage


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
    print(f"Hello from Cloud Run Job: {job_name}")

    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        print("GCS_BUCKET が未設定のためログ書き出しをスキップ")
        return

    log_data = {
        "job": job_name,
        "status": "success",
        "message": f"Hello from Cloud Run Job: {job_name}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    path = upload_log(bucket_name, job_name, log_data)
    print(f"ログ書き出し完了: gs://{bucket_name}/{path}")


if __name__ == "__main__":
    main()
