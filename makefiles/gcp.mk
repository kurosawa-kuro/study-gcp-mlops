# === GCPセットアップ ===
TF_SA := terraform@$(PROJECT_ID).iam.gserviceaccount.com

.PHONY: gcp-setup-docker gcp-setup-apis gcp-setup-sa

gcp-setup-apis:
	gcloud services enable \
	  artifactregistry.googleapis.com \
	  run.googleapis.com \
	  compute.googleapis.com \
	  iam.googleapis.com \
	  cloudresourcemanager.googleapis.com \
	  cloudscheduler.googleapis.com \
	  bigquery.googleapis.com \
	  --project=$(PROJECT_ID)

gcp-setup-sa:
	gcloud projects add-iam-policy-binding $(PROJECT_ID) \
	  --member="serviceAccount:$(TF_SA)" \
	  --role="roles/editor" --quiet
	gcloud projects add-iam-policy-binding $(PROJECT_ID) \
	  --member="serviceAccount:$(TF_SA)" \
	  --role="roles/run.admin" --quiet

gcp-setup-docker:
	gcloud auth configure-docker $(REGION)-docker.pkg.dev

gcp-setup: gcp-setup-apis gcp-setup-sa gcp-setup-docker
