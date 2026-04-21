.DEFAULT_GOAL := help

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: help build seed train serve test all down clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

build: ## Build Docker images (docker compose build)
	docker compose build

seed: ## Seed sklearn California Housing into PostgreSQL
	$(PYTHON) scripts/ml/seed.py

train: ## Run LightGBM training → models/{run_id}/
	$(PYTHON) scripts/ml/train.py

serve: ## Start FastAPI on :8000 (docker compose up api)
	$(PYTHON) scripts/app/serve.py

test: ## Run pytest (local)
	$(PYTHON) scripts/test.py

all: build seed train ## build → seed → train

down: ## Stop and remove docker compose services
	docker compose down --remove-orphans

clean: ## docker compose down + remove generated files
	$(PYTHON) scripts/clean.py
