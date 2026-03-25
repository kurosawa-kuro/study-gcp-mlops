# === ml (学習パイプライン) ===
ML_IMAGE := ml-train
ML_IMAGE_URI := $(IMAGE_BASE)/$(ML_IMAGE):$(TAG)

.PHONY: ml-test ml-run-local ml-build ml-push ml-ui

ml-test:  ## MLテスト実行
	cd src/ml && pip install -q -r requirements-dev.txt && PYTHONPATH=. pytest -v test_train.py

ml-run-local:  ## ローカルでML学習実行
	cd src/ml && pip install -q -r requirements.txt && PYTHONPATH=. python3 main.py

ml-build:  ## MLイメージビルド
	docker build -t $(ML_IMAGE_URI) ./src/ml/

ml-push: ml-build  ## MLイメージ push
	docker push $(ML_IMAGE_URI)

ml-ui:  ## MLflow UI起動（http://localhost:5000）
	cd src/ml && mlflow ui --host 0.0.0.0 --port 5000
