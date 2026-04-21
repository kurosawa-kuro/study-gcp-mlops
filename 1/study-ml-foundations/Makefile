.DEFAULT_GOAL := help

.PHONY: help build seed train serve test all down clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

build: ## Build Docker images (docker compose build)
	docker compose build

seed: ## Seed sklearn California Housing into PostgreSQL
	./scripts/ml/seed.sh

train: ## Run LightGBM training → models/{run_id}/
	./scripts/ml/train.sh

serve: ## Start FastAPI on :8000 (docker compose up api)
	./scripts/api/serve.sh

test: ## Run pytest (local)
	./scripts/test.sh

all: build seed train ## build → seed → train

down: ## Stop and remove docker compose services
	docker compose down --remove-orphans

clean: ## docker compose down + remove generated files
	./scripts/clean.sh
