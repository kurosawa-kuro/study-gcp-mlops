# === batch (Cloud Run Job) ===
BATCH_IMAGE := ml-batch
BATCH_IMAGE_URI := $(IMAGE_BASE)/$(BATCH_IMAGE):$(TAG)

.PHONY: batch-build batch-push batch-deploy batch-run batch-logs batch-test batch-monitor batch-drift batch-run-local batch-ui

batch-test:  ## テスト実行
	cd src/batch && pip install -q -r requirements-dev.txt && PYTHONPATH=. pytest -v test_main.py test_e2e.py

batch-run-local:  ## ローカルでML学習実行
	cd src/batch && pip install -q -r requirements.txt && PYTHONPATH=. python3 main.py

batch-build:  ## Dockerイメージビルド
	docker build -t $(BATCH_IMAGE_URI) ./src/batch/

batch-push: batch-build  ## ビルド & push
	docker push $(BATCH_IMAGE_URI)

batch-deploy: tf-apply-repo batch-push tf-apply  ## 冪等デプロイ

batch-run:  ## Cloud Run Job実行
	gcloud run jobs execute $(BATCH_IMAGE) \
	  --region=$(REGION) \
	  --project=$(PROJECT_ID)

batch-logs:  ## 実行履歴確認
	gcloud run jobs executions list \
	  --job=$(BATCH_IMAGE) \
	  --region=$(REGION) \
	  --project=$(PROJECT_ID)

batch-monitor:  ## 監視 + Discord通知
	python3 scripts/monitor_batch.py

batch-drift:  ## モデルドリフト検知
	python3 scripts/check_drift.py

batch-ui:  ## MLflow UI起動（http://localhost:5000）
	cd src/batch && mlflow ui --host 0.0.0.0 --port 5000
