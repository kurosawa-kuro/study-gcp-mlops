# === api (Cloud Run Service) ===
API_IMAGE := ml-api
API_IMAGE_URI := $(IMAGE_BASE)/$(API_IMAGE):$(TAG)

.PHONY: api-build api-push api-deploy api-logs

api-build:
	docker build -t $(API_IMAGE_URI) ./src/api/

api-push: api-build
	docker push $(API_IMAGE_URI)

api-deploy: tf-apply-repo api-push tf-apply

api-logs:
	gcloud run services logs read $(API_IMAGE) \
	  --region=$(REGION) \
	  --project=$(PROJECT_ID)
