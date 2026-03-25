resource "google_artifact_registry_repository" "myrepo" {
  location      = var.region
  repository_id = var.repo_name
  format        = "DOCKER"
  description   = "MLOps Docker repository"
}