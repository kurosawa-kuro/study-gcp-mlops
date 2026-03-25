resource "google_cloud_run_v2_job" "ml_batch" {
  name     = "ml-batch"
  location = var.region

  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_name}/ml-batch:latest"

        env {
          name  = "GCS_BUCKET"
          value = var.bucket_name
        }

        env {
          name  = "JOB_NAME"
          value = "ml-batch"
        }

        env {
          name  = "BQ_DATASET"
          value = "mlops"
        }
      }
    }
  }

  # CI/CDがgcloud run jobs updateでイメージを更新するため、
  # templateの変更はTerraform管理外とする（ドリフト防止）
  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_artifact_registry_repository.myrepo,
    google_storage_bucket.data,
  ]
}
