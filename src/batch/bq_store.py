import os
import time


def _get_bq_client():
    from google.cloud import bigquery
    return bigquery.Client()


def insert_metrics(row: dict, max_retries: int = 3) -> None:
    """評価メトリクスをBigQueryに投入する。リトライ付き。"""
    dataset = os.environ.get("BQ_DATASET", "mlops")
    table = os.environ.get("BQ_TABLE", "metrics")
    project = os.environ.get("GCP_PROJECT", "mlops-dev-a")

    table_id = f"{project}.{dataset}.{table}"
    client = _get_bq_client()

    for attempt in range(max_retries):
        errors = client.insert_rows_json(table_id, [row])
        if not errors:
            return
        if attempt < max_retries - 1:
            wait = 2 ** attempt
            print(f"BigQuery insert リトライ ({attempt + 1}/{max_retries}), {wait}秒待機...")
            time.sleep(wait)

    raise RuntimeError(f"BigQuery insert エラー ({max_retries}回失敗): {errors}")
