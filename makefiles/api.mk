# === api (Cloud Run Service) ===
API_IMAGE := ml-api
API_IMAGE_URI := $(IMAGE_BASE)/$(API_IMAGE):$(TAG)

.PHONY: api-test api-build api-push api-deploy api-logs api-url api-monitor

api-test:  ## APIテスト実行
	cd src/api && pip install -q -r requirements-dev.txt && PYTHONPATH=. pytest -v test_main.py

api-build:  ## APIイメージビルド
	docker build -t $(API_IMAGE_URI) ./src/api/

api-push: api-build  ## APIイメージ push
	docker push $(API_IMAGE_URI)

api-deploy: tf-apply-repo api-push tf-apply  ## API冪等デプロイ

api-logs:  ## APIログ確認
	gcloud run services logs read $(API_IMAGE) \
	  --region=$(REGION) \
	  --project=$(PROJECT_ID)

api-url:  ## APIのURL表示
	@gcloud run services describe $(API_IMAGE) \
	  --region=$(REGION) \
	  --project=$(PROJECT_ID) \
	  --format='value(status.url)'

api-monitor:  ## API健全性チェック + Discord通知
	python3 scripts/monitor_api.py
