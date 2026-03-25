resource "google_bigquery_dataset" "mlops" {
  dataset_id                 = "mlops"
  location                   = var.region
  default_table_expiration_ms = 7776000000 # 90日（ミリ秒）
}

resource "google_bigquery_table" "metrics" {
  dataset_id          = google_bigquery_dataset.mlops.dataset_id
  table_id            = "metrics"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
    expiration_ms = 7776000000 # 90日
  }

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "rmse", type = "FLOAT64", mode = "REQUIRED" },
    { name = "mae", type = "FLOAT64", mode = "REQUIRED" },
    { name = "model_path", type = "STRING", mode = "NULLABLE" },
    { name = "n_estimators", type = "INT64", mode = "NULLABLE" },
    { name = "max_depth", type = "INT64", mode = "NULLABLE" },
  ])
}
