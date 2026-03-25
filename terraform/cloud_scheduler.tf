resource "google_cloud_scheduler_job" "ml_batch_schedule" {
  name      = "ml-batch-schedule"
  region    = var.region
  schedule  = "0 9 * * *"
  time_zone = "Asia/Tokyo"

  http_target {
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/ml-batch:run"
    http_method = "POST"

    oauth_token {
      service_account_email = "${data.google_project.current.number}-compute@developer.gserviceaccount.com"
    }
  }

  depends_on = [google_cloud_run_v2_job.ml_batch]
}
