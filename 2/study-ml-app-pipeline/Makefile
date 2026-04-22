.DEFAULT_GOAL := help

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: help build seed train serve test all down clean free-ports

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

# TBD: Phase 1 の Makefile から必要な target を移植する。現状 skeleton。

build: ## (TBD) Build Docker images
	@echo "TBD: docker compose build"

seed: ## (TBD) Seed California Housing into PostgreSQL
	@echo "TBD: docker compose run --rm seed"

train: ## (TBD) Run LightGBM training via train_job pipeline
	@echo "TBD: docker compose run --rm trainer"

serve: ## (TBD) Start FastAPI on :8000
	@echo "TBD: $(PYTHON) scripts/local/deploy/serve.py"

test: ## (TBD) Run pytest
	@echo "TBD: $(PYTHON) -m pytest"

all: build seed train ## (TBD) build → seed → train

down: ## (TBD) Stop docker compose services
	@echo "TBD: docker compose down --remove-orphans"

clean: ## (TBD) docker down + clean generated files
	@echo "TBD: cleanup"

free-ports: ## (TBD) Free host :5432 / :8000 from other projects
	@echo "TBD: free host ports"
