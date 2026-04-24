SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Absolute paths keep targets idempotent regardless of invocation cwd.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
TF_DIR := $(ROOT)/infra/terraform/environments/dev

# Project-wide non-credential settings live in env/config/setting.yaml so
# Python (scripts/_common.py) and Make read from one source of truth. We
# parse the flat key:value file with awk (faster than `uv run python` and
# already a Make hard dep for the help target).
SETTINGS_FILE := $(ROOT)/env/config/setting.yaml
_yaml_get = $(strip $(shell awk -F: '/^$(1):/ {gsub(/^[ "'\'']+|[ "'\'']+$$/,"",$$2); print $$2; exit}' $(SETTINGS_FILE)))

PROJECT_ID    ?= $(call _yaml_get,project_id)
REGION        ?= $(call _yaml_get,region)
API_SERVICE   ?= $(call _yaml_get,api_service)
TRAINING_JOB  ?= $(call _yaml_get,training_job)
ARTIFACT_REPO ?= $(call _yaml_get,artifact_repo)
VERTEX_LOCATION ?= $(call _yaml_get,vertex_location)
PIPELINE_ROOT_BUCKET ?= $(call _yaml_get,pipeline_root_bucket)
PIPELINE_TEMPLATE_GCS_PATH ?= $(call _yaml_get,pipeline_template_gcs_path)

# Override-able via CLI: `make tf-plan GITHUB_REPO=other/repo ONCALL_EMAIL=...`
GITHUB_REPO   ?= $(call _yaml_get,github_repo)
ONCALL_EMAIL  ?= $(call _yaml_get,oncall_email)

# Local model path produced by `make train-smoke-persist`.
MODEL_PATH_OVERRIDE ?= /tmp/hybrid-search-cloud-smoke-model.txt

# deploy-monitor 出力先 (ops-deploy-monitor が tee する log を保存)
MONITOR_LOG_DIR ?= $(ROOT)/logs/deploy-monitor

export PROJECT_ID REGION API_SERVICE TRAINING_JOB ARTIFACT_REPO VERTEX_LOCATION PIPELINE_ROOT_BUCKET PIPELINE_TEMPLATE_GCS_PATH

.PHONY: help doctor sync test lint fmt fmt-check typecheck check \
        check-layers sync-dataform-config \
        tf-bootstrap tf-init tf-validate tf-fmt tf-fmt-fix tf-plan \
        setup-model-monitoring setup-pipeline-schedule \
        deploy-all deploy-all-direct run-all destroy-all seed-test seed-test-clean \
        train-smoke train-smoke-persist api-dev clean \
        docker-auth deploy-api-local deploy-training-job-local \
        ops-deploy-monitor ops-monitor \
        ops-api-url ops-daily ops-livez ops-search ops-search-components ops-ranking ops-feedback ops-enable-search \
        ops-accuracy-report local-accuracy-report \
        ops-skew-latest ops-search-volume ops-runs-recent \
	ops-skew-run ops-train-now ops-pipeline-run ops-promote-reranker ops-reload-api \
        ops-check-retrain ops-bq-scan-top ops-label-seed

help: ## Show this help
	@echo "First-time setup:  see README.md §セットアップ (run 'make doctor' to verify tools)"
	@echo "Quick start:       make sync && make check && make train-smoke"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

doctor: ## Verify that prerequisite tools are installed
	uv run python -m scripts.local.setup.doctor

# ----- Python workspace -----

sync: ## uv sync (single root package + dev group)
	uv sync --dev

test: ## Run pytest across the workspace
	uv run pytest

lint: ## ruff check
	uv run ruff check .

fmt: ## ruff format (writes)
	uv run ruff format .

fmt-check: ## ruff format --check
	uv run ruff format --check .

typecheck: ## mypy strict
	uv run mypy app ml pipeline

check: lint fmt-check typecheck test ## Run all CI-equivalent checks

sync-dataform-config: ## Regenerate pipeline/data_job/dataform/workflow_settings.yaml
	uv run python -m scripts.ci.sync_dataform

check-layers: ## AST-based layer boundary check (Ports / pure logic must not import concrete adapters or SDKs)
	uv run python -m scripts.ci.layers

# ----- Terraform -----

tf-bootstrap: ## Phase 0: enable APIs + create tfstate bucket (idempotent, needs project owner rights)
	uv run python -m scripts.local.setup.tf_bootstrap

tf-init: ## terraform init (with tfstate bucket preflight check)
	uv run python -m scripts.local.setup.tf_init

tf-validate: ## terraform validate (backend-less, works offline)
	terraform -chdir=$(TF_DIR) init -backend=false -upgrade=false >/dev/null
	terraform -chdir=$(TF_DIR) validate

tf-fmt: ## terraform fmt --check
	terraform -chdir=$(TF_DIR) fmt -check -diff

tf-fmt-fix: ## terraform fmt (writes)
	terraform -chdir=$(TF_DIR) fmt

tf-plan: ## terraform plan (requires GITHUB_REPO + ONCALL_EMAIL; saves tfplan)
	uv run python -m scripts.local.setup.tf_plan

setup-model-monitoring: ## Print resolved Vertex Model Monitoring setup payload
	uv run python -m scripts.local.setup.setup_model_monitoring

setup-pipeline-schedule: ## Print resolved Vertex Pipeline schedule setup payload
	uv run python -m scripts.local.setup.create_schedule

deploy-all: ## End-to-end provisioning + search-api rollout (tf-bootstrap → apply → deploy-api-local)
	uv run python -m scripts.local.setup.deploy_all

deploy-all-direct: ## Compatibility alias of deploy-all (Phase4 naming)
	$(MAKE) deploy-all

ops-deploy-monitor: ## Real-time monitor: runs deploy-all and reports live step/build stall status
	@mkdir -p "$(MONITOR_LOG_DIR)"
	@log_file="$(MONITOR_LOG_DIR)/$$(date -u +%Y%m%dT%H%M%SZ)-deploy-monitor.log"; \
	echo "monitor-log: $$log_file"; \
	bash -o pipefail -c 'uv run python -u -m scripts.local.deploy_monitor 2>&1 | tee "$$0"' "$$log_file"

ops-monitor: ## Generic monitor: CMD="<command>" [LABEL=<name>] (例: make ops-monitor CMD="make deploy-api-local")
	@if [ -z "$(CMD)" ]; then echo "usage: make ops-monitor CMD=\"<command>\" [LABEL=<name>]" >&2; exit 2; fi
	@mkdir -p "$(MONITOR_LOG_DIR)"
	@label="$${LABEL:-cmd}"; \
	log_file="$(MONITOR_LOG_DIR)/$$(date -u +%Y%m%dT%H%M%SZ)-$$label-monitor.log"; \
	echo "monitor-log: $$log_file"; \
	bash -o pipefail -c 'uv run python -u -m scripts.local.deploy_monitor --label "$$0" -- $$1 2>&1 | tee "$$2"' "$$label" "$(CMD)" "$$log_file"

run-all: ## End-to-end validation flow after deploy (layer check → seed → train pipeline submit → smoke APIs → daily ops)
	$(MAKE) check-layers
	$(MAKE) seed-test
	$(MAKE) ops-train-now
	$(MAKE) ops-livez
	$(MAKE) ops-search
	$(MAKE) ops-search-components
	$(MAKE) ops-feedback
	$(MAKE) ops-ranking
	$(MAKE) ops-label-seed
	$(MAKE) ops-daily
	$(MAKE) ops-accuracy-report

destroy-all: ## Tear down every Terraform-managed resource (no prompt — PDCA loop, pair with deploy-all)
	uv run python -m scripts.local.setup.destroy_all

seed-test: ## Insert 5 test properties for PDCA smoke
	uv run python -m scripts.local.setup.seed_minimal

seed-test-clean: ## Drop the test seed data (benign if absent)
	uv run python -m scripts.local.setup.seed_minimal_clean

# ----- App / Job smoke commands (local) -----

train-smoke: ## Dry-run the ranker training job locally (synthetic data, no GCS/BQ)
	uv run rank-train --dry-run

train-smoke-persist: ## Dry-run ranker trainer and copy the model to $(MODEL_PATH_OVERRIDE)
	uv run rank-train --dry-run --save-to "$(MODEL_PATH_OVERRIDE)"

api-dev: ## Start uvicorn locally (rerank-free /search requires ENABLE_SEARCH=1 + BQ creds)
	ENABLE_SEARCH=false uv run uvicorn app.main:app --reload

# ----- Local deploy path (bypasses CI; uses Cloud Build) -----

docker-auth: ## (Optional) configure local docker for Artifact Registry
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet

deploy-api-local: ## Cloud Build + `gcloud run deploy` search-api
	uv run python -m scripts.local.deploy.api_local

deploy-training-job-local: ## Deprecated: training moved to Vertex Pipelines
	@echo "training-job は廃止済みです。make ops-train-now を使ってください。"

# ----- Housekeeping -----

clean: ## Remove caches (.venv, .terraform, pyc)
	rm -rf .venv $(TF_DIR)/.terraform
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache \) -prune -exec rm -rf {} +

# ----- GCP operations (see docs/04_運用.md §3) -----

ops-api-url: ## Print the search-api Cloud Run URL
	@gcloud run services describe $(API_SERVICE) --project=$(PROJECT_ID) --region=$(REGION) --format='value(status.url)'

ops-daily: ops-skew-latest ops-search-volume ops-runs-recent ## Run the 3 core daily checks

ops-skew-latest: ## Today's per-feature skew detection results (validation_results)
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/local/sql/skew_latest.sql

ops-search-volume: ## /search request volume over the last 24h
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/local/sql/search_volume.sql

ops-runs-recent: ## Last 5 LightGBM LambdaRank training runs
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/local/sql/runs_recent.sql

ops-skew-run: ## Ad-hoc execution of monitoring/validate_feature_skew.sql
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < monitoring/validate_feature_skew.sql

ops-bq-scan-top: ## Top 20 BQ scans in the last 7 days (cost audit)
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/local/sql/bq_scan_top.sql

ops-train-now: ## Submit train pipeline to Vertex AI
	uv run python -m pipeline.workflow.compile --target train --output-dir dist/pipelines --submit --project-id $(PROJECT_ID) --location $(VERTEX_LOCATION) --pipeline-root gs://$(PIPELINE_ROOT_BUCKET)/runs --service-account sa-pipeline@$(PROJECT_ID).iam.gserviceaccount.com

ops-pipeline-run: ## Submit a pipeline manually: TARGET=embed|train PARAM='key=value'
	uv run python -m pipeline.workflow.compile --target $${TARGET:-train} --output-dir dist/pipelines --submit --project-id $(PROJECT_ID) --location $(VERTEX_LOCATION) --pipeline-root gs://$(PIPELINE_ROOT_BUCKET)/runs --service-account sa-pipeline@$(PROJECT_ID).iam.gserviceaccount.com $${PARAM:+--parameter $$PARAM}

ops-promote-reranker: ## Print or apply reranker promotion plan: VERSION=vN APPLY=1
	uv run python -m scripts.local.ops.promote reranker $${VERSION:-v1} $${APPLY:+--apply}

ops-reload-api: ## Bump FORCE_RELOAD env so search-api picks up the latest model
	gcloud run services update $(API_SERVICE) --project=$(PROJECT_ID) --region=$(REGION) --update-env-vars="FORCE_RELOAD=$$(date +%s)"

ops-enable-search: ## Flip search-api to Vertex endpoint mode
	gcloud run services update $(API_SERVICE) --project=$(PROJECT_ID) --region=$(REGION) --update-env-vars="ENABLE_SEARCH=true,ENABLE_RERANK=$${RERANKER_ENDPOINT_ID:+true},VERTEX_LOCATION=$(VERTEX_LOCATION),VERTEX_ENCODER_ENDPOINT_ID=$${ENCODER_ENDPOINT_ID:?set ENCODER_ENDPOINT_ID},VERTEX_RERANKER_ENDPOINT_ID=$${RERANKER_ENDPOINT_ID:-}"

ops-livez: ## Hit /livez on the deployed search-api (IAM-gated)
	uv run python -m scripts.local.ops.livez_check

ops-slo-status: ## Phase 6 T5: print current compliance + burn-rate (1h/3d) for availability + latency SLOs
	uv run python -m scripts.local.ops.slo_status

bqml-train-popularity: ## Phase 6 T1: train BQML property-popularity model (BOOSTED_TREE_REGRESSOR)
	uv run python -m scripts.local.bqml.train_popularity

enrich-properties: ## Phase 6 T8: run Gemini description enrichment (LIMIT=50 BATCH=10)
	uv run python -m scripts.local.enrichment.run_enrichment --limit=$${LIMIT:-50} --batch-size=$${BATCH:-10}

ops-search: ## POST /search smoke (override QUERY/TOP_K/MAX_RENT env vars)
	uv run python -m scripts.local.ops.search_check

ops-search-components: ## Strict gate: lexical/semantic/rerank contributions must all be non-zero
	uv run python -m scripts.local.ops.search_component_check

ops-ranking: ## POST /search and inspect lexical_rank / final_rank / score / me5_score
	uv run python -m scripts.local.ops.ranking_check

ops-feedback: ## /search → /feedback round-trip (publisher path smoke)
	uv run python -m scripts.local.ops.feedback_check

ops-label-seed: ## Seed feedback events (click/favorite/inquiry) against /search
	uv run python -m scripts.local.ops.training_label_seed

ops-check-retrain: ## POST /jobs/check-retrain with OIDC; pipe to jq
	uv run python -m scripts.local.ops.check_retrain

ops-accuracy-report: ## Simple ranking accuracy report on deployed Cloud Run (/search, TARGET=gcp)
	TARGET=gcp uv run python -m scripts.local.ops.accuracy_report

local-accuracy-report: ## Simple ranking accuracy report against local API (/search, TARGET=local)
	TARGET=local uv run python -m scripts.local.ops.accuracy_report
