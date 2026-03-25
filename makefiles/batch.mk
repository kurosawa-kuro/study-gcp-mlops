# === batch (Cloud Run Job) ===
BATCH_IMAGE := ml-batch
BATCH_IMAGE_URI := $(IMAGE_BASE)/$(BATCH_IMAGE):$(TAG)

.PHONY: batch-build batch-push batch-deploy batch-run batch-logs batch-test batch-monitor

batch-test:
	cd src/batch && pip install -q -r requirements-dev.txt && pytest -v test_main.py

batch-build:
	docker build -t $(BATCH_IMAGE_URI) ./src/batch/

batch-push: batch-build
	docker push $(BATCH_IMAGE_URI)

batch-deploy: tf-apply-repo batch-push tf-apply

batch-run:
	gcloud run jobs execute $(BATCH_IMAGE) \
	  --region=$(REGION) \
	  --project=$(PROJECT_ID)

batch-logs:
	gcloud run jobs executions list \
	  --job=$(BATCH_IMAGE) \
	  --region=$(REGION) \
	  --project=$(PROJECT_ID)

batch-monitor:
	python3 scripts/monitor_batch.py
