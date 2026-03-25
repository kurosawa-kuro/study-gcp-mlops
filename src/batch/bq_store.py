import os


def _get_bq_client():
    from google.cloud import bigquery
    return bigquery.Client()


def insert_metrics(row: dict) -> None:
    """評価メトリクスをBigQueryに投入する。"""
    dataset = os.environ.get("BQ_DATASET", "mlops")
    table = os.environ.get("BQ_TABLE", "metrics")
    project = os.environ.get("GCP_PROJECT", "mlops-dev-a")

    table_id = f"{project}.{dataset}.{table}"

    client = _get_bq_client()
    errors = client.insert_rows_json(table_id, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert エラー: {errors}")
