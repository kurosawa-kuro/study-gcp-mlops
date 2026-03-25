resource "google_cloud_run_v2_service" "ml_api" {
  name     = "ml-api"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_name}/ml-api:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }

      env {
        name  = "BQ_DATASET"
        value = "mlops"
      }
    }
  }

  # CI/CDがgcloud run services updateでイメージを更新するため、
  # templateの変更はTerraform管理外とする（ドリフト防止）
  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_artifact_registry_repository.myrepo,
    google_bigquery_table.metrics,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.ml_api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
