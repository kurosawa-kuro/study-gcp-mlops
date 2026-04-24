.DEFAULT_GOAL := help

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(if $(wildcard ../.venv/bin/python),../.venv/bin/python,python3))
MONITOR_LOG_DIR ?= logs/run-all-monitor

# docker compose を直接呼ばず、env/secret/credential.yaml を読み込むラッパー経由で起動する
DOCKER_COMPOSE ?= ./scripts/local/setup/compose.sh

.PHONY: \
	help up build down logs test test-e2e install-browsers sync api-refresh ports-free up-clean \
	wait-db \
	check-layers \
	db-migrate-core db-seed-properties db-migrate-ops db-migrate-features db-migrate-embeddings db-migrate-learning db-migrate-eval \
	ops-sync ops-livez ops-search ops-search-components ops-feedback ops-ranking ops-ranking-verbose ops-label-seed ops-accuracy-report \
	features-daily features-report \
	ops-embed \
	ops-train-build ops-train-fit ops-train-fit-safe \
	eval-compare eval-offline kpi-daily eval-weekly-report ops-retrain \
	ops-bootstrap ops-daily ops-weekly run-all-core run-all ops-run-all-monitor verify-pipeline

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

up: ## Start docker compose services (detached)
	$(DOCKER_COMPOSE) up -d

ports-free: ## Free host ports 8000/5432/5050/7700/6379 (stop foreign containers)
	./scripts/local/setup/free_ports.sh

up-clean: ports-free up ## Free ports then start docker compose (safe bring-up)

wait-db: ## Wait until postgres accepts connections
	@$(DOCKER_COMPOSE) exec -T postgres sh -lc 'for i in $$(seq 1 15); do pg_isready -U "$${POSTGRES_USER:-admin}" -d "$${POSTGRES_DB:-estate}" >/dev/null 2>&1 && exit 0; sleep 1; done; echo "postgres is not ready after 15s" >&2; exit 1'

build: ## Build the api docker image
	$(DOCKER_COMPOSE) build api

down: ## Stop docker compose services
	$(DOCKER_COMPOSE) down

logs: ## Tail api/postgres/meili/pgadmin/redis logs
	$(DOCKER_COMPOSE) logs -f api postgres meilisearch pgadmin redis

sync: ## uv sync (root package + dev group)
	uv sync --dev

test: ## Run pytest (local, E2E は除外)
	PYTHONPATH=app:common/src:pipeline/batch:pipeline:ml $(PYTHON) -m pytest tests/ app/tests/ common/tests/ tests/unit/pipeline/ -v -m "not e2e"

test-e2e: ## Run Playwright E2E tests (要 install-browsers)
	PYTHONPATH=app:common/src:pipeline/batch:pipeline:ml $(PYTHON) -m pytest tests/e2e -v -m e2e

install-browsers: ## Playwright 用の Chromium バイナリをインストール
	$(PYTHON) -m playwright install chromium

check-layers: ## Enforce layer boundaries by AST (stage=5)
	$(PYTHON) scripts/ci/layers.py --stage 5

api-refresh: ## Rebuild and recreate only the api service
	$(DOCKER_COMPOSE) build api
	$(DOCKER_COMPOSE) up -d --force-recreate api

# ----- DB migrations -----

db-migrate-core: ## Migration 001: create properties
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.run_migrations infra/run/jobs/migrations/001_create_properties.sql

db-seed-properties: ## Migration 002: seed properties
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.seed_properties_from_dataset

db-migrate-ops: ## Migration 003: create logs and stats
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.run_migrations infra/run/jobs/migrations/003_create_logs_and_stats.sql

db-migrate-features: ## Migration 004: features + batch logs
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.run_migrations infra/run/jobs/migrations/004_features_and_batch_logs.sql

db-migrate-embeddings: ## Migration 005: me5 embeddings
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.run_migrations infra/run/jobs/migrations/005_me5.sql

db-migrate-learning: ## Migration 006+007: learning logs + ranking compare logs
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.run_migrations infra/run/jobs/migrations/006_learning_logs.sql
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.run_migrations infra/run/jobs/migrations/007_ranking_compare_logs.sql

db-migrate-eval: ## Migration 008: eval + kpi tables
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.maintenance.run_migrations infra/run/jobs/migrations/008_eval_and_kpi.sql

# ----- Search / ops smoke (aligned with Phase 3/4 ops-* naming) -----

ops-sync: ## Sync properties from PostgreSQL → Meilisearch
	$(DOCKER_COMPOSE) exec -T api python -m ml.data.loaders.sync_properties_to_meilisearch

ops-livez: ## Health check against the running api (aligned with Phase 3/4 ops-livez)
	$(PYTHON) scripts/local/ops/health_check.py

ops-search: ## POST /search smoke
	$(PYTHON) scripts/local/ops/search_check.py

ops-search-components: ## Strict gate: Meili/ME5/LightGBM contributions must be non-zero
	$(PYTHON) scripts/local/ops/search_component_check.py

ops-feedback: ## /search → /feedback round-trip smoke
	$(PYTHON) scripts/local/ops/feedback_check.py

ops-ranking: ## POST /search and inspect rerank output
	$(PYTHON) scripts/local/ops/ranking_check.py

ops-ranking-verbose: ## Detailed rerank inspection (lgbm_score / me5_score)
	$(PYTHON) scripts/local/ops/ranking_check_verbose.py

ops-label-seed: ## Seed feedback events (click/favorite/inquiry)
	$(PYTHON) scripts/local/ops/training_label_seed.py

ops-accuracy-report: ## Simple ranking accuracy report (/search -> nDCG/HitRate/MRR)
	$(PYTHON) scripts/local/ops/accuracy_report.py

# ----- Feature / embedding batch -----

features-daily: ## Daily feature aggregation
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.features.aggregate_daily_property_stats

features-report: ## Export feature report
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.features.export_feature_report

ops-embed: ## Generate property embeddings (ME5)
	$(DOCKER_COMPOSE) exec -T api python -m ml.data.preprocess.generate_property_embeddings

# ----- Training -----

ops-train-build: ## Build training dataset
	$(DOCKER_COMPOSE) exec -T api python -m ml.training.model_builder

ops-train-fit: ## Fit LightGBM LambdaRank model
	$(DOCKER_COMPOSE) exec -T api python -m ml.training.trainer

ops-train-fit-safe: ## Fit LightGBM with graceful fallback on empty data
	$(PYTHON) scripts/local/ops/training_fit_safe.py

# ----- Evaluation -----

eval-compare: ## Export ranking compare report (Meili vs rerank)
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.evaluation.export_ranking_compare_report

eval-offline: ## Offline NDCG / MAP / Recall evaluation
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.evaluation.run_offline_evaluation

kpi-daily: ## Daily KPI aggregation (CTR / favorite / inquiry)
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.evaluation.aggregate_daily_kpi

eval-weekly-report: ## Export weekly evaluation report
	$(DOCKER_COMPOSE) exec -T api python -m pipeline.batch.evaluation.export_weekly_evaluation_report

ops-retrain: ## Weekly retraining orchestration
	$(DOCKER_COMPOSE) exec -T api python -m ml.training.job

# ----- Aggregates -----

ops-bootstrap: wait-db db-migrate-core db-seed-properties db-migrate-ops db-migrate-features db-migrate-embeddings db-migrate-learning db-migrate-eval ops-sync ops-embed ops-label-seed ops-train-build ops-train-fit-safe ## One-time setup (migrations + seed + index + model prep)

ops-daily: ## Daily sync/feature/embed/kpi tasks
	$(MAKE) ops-sync
	$(MAKE) features-daily
	$(MAKE) ops-embed
	$(MAKE) kpi-daily

ops-weekly: ## Weekly evaluate/report/retrain tasks
	$(MAKE) eval-compare
	$(MAKE) eval-offline
	$(MAKE) eval-weekly-report
	$(MAKE) ops-retrain

verify-pipeline: ## Representative end-to-end smoke checks (auto-clean conflicts)
	$(MAKE) up-clean
	$(MAKE) ops-bootstrap
	$(MAKE) check-layers
	$(MAKE) ops-livez
	$(MAKE) ops-search
	$(MAKE) ops-search-components
	$(MAKE) ops-feedback
	$(MAKE) ops-ranking
	$(MAKE) ops-ranking-verbose
	$(MAKE) ops-accuracy-report
	$(MAKE) eval-compare
	$(MAKE) eval-offline

run-all-core: ## Core local validation flow (includes component + accuracy report)
	$(MAKE) verify-pipeline

ops-run-all-monitor: ## Monitor run-all progress and save logs
	@mkdir -p "$(MONITOR_LOG_DIR)"
	@log_file="$(MONITOR_LOG_DIR)/$$(date -u +%Y%m%dT%H%M%SZ)-run-all.log"; \
	echo "monitor-log: $$log_file"; \
	$(PYTHON) scripts/local/run_all_monitor.py --log-file "$$log_file" -- $(MAKE) run-all-core

run-all: ops-run-all-monitor ## End-to-end local validation flow via monitor
