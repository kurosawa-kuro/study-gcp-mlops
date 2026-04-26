locals {
  required_apis = [
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "run.googleapis.com", # Meilisearch は引き続き Cloud Run
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "dataform.googleapis.com",
    "pubsub.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "eventarc.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "notebooks.googleapis.com",
    # Phase 6: GKE + Gateway API + IAP
    "container.googleapis.com",
    "gkehub.googleapis.com",
    "iap.googleapis.com",
    "networkservices.googleapis.com",
    "certificatemanager.googleapis.com",
    # Phase 6 PMLE: Dataflow streaming
    "dataflow.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each           = toset(local.required_apis)
  service            = each.value
  disable_on_destroy = false
}
