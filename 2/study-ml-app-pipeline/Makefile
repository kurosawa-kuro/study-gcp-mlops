.DEFAULT_GOAL := help

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
MONITOR_LOG_DIR ?= logs/run-all-monitor

.PHONY: help build seed train serve test test-e2e install-browsers all run-all-core run-all ops-run-all-monitor down clean free-ports

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

build: ## Build Docker images (docker compose build)
	docker compose build

seed: ## Seed sklearn California Housing into PostgreSQL
	$(PYTHON) scripts/local/setup/seed.py

train: ## Run LightGBM training
	$(PYTHON) scripts/local/setup/train.py

serve: ## Start FastAPI on :8000
	$(PYTHON) scripts/local/deploy/serve.py

test: ## Run pytest (local, E2E は除外)
	$(PYTHON) scripts/local/ops/test.py -m "not e2e"

test-e2e: ## Run Playwright E2E tests (要 install-browsers)
	$(PYTHON) scripts/local/ops/test.py -m e2e

install-browsers: ## Playwright 用の Chromium などブラウザをインストール
	$(PYTHON) -m playwright install chromium

all: build seed train ## build → seed → train

run-all-core: all test ## Core flow (build → seed → train → test)

ops-run-all-monitor: ## Monitor run-all progress and save logs
	@mkdir -p "$(MONITOR_LOG_DIR)"
	@log_file="$(MONITOR_LOG_DIR)/$$(date -u +%Y%m%dT%H%M%SZ)-run-all.log"; \
	echo "monitor-log: $$log_file"; \
	$(PYTHON) scripts/local/deploy_monitor.py --label run-all --log-file "$$log_file" -- "$(MAKE)" run-all-core

run-all: ops-run-all-monitor ## End-to-end local flow via monitor (build → seed → train → test)

down: ## Stop and remove docker compose services
	docker compose down --remove-orphans

clean: ## docker compose down + remove generated files
	$(PYTHON) scripts/local/ops/clean.py

free-ports: ## Stop non-project containers binding host :5432/:8000
	$(PYTHON) -c "import sys; sys.path.insert(0, 'scripts'); from core import free_host_ports; free_host_ports()"
