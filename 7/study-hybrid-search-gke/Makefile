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

# deploy-monitor log output directory.
MONITOR_LOG_DIR ?= $(ROOT)/logs/deploy-monitor

PHASE_NAME := phase-7-gke
NA_TARGETS := up down wait-db free-ports build seed serve test-e2e install-browsers \
	db-migrate-% db-seed-% ops-bootstrap \
	ops-sync ops-embed ops-train-build ops-train-fit ops-ranking-verbose \
	ops-weekly \
	eval-compare eval-offline kpi-daily eval-weekly-report features-daily features-report \
	deploy-api-local \
	api-dev-search-rerank setup-encoder-endpoint setup-reranker-endpoint \
	ops-monitor ops-monitor-lro ops-enable-search

include ../../mk/base.mk

export PROJECT_ID REGION API_SERVICE TRAINING_JOB ARTIFACT_REPO VERTEX_LOCATION PIPELINE_ROOT_BUCKET PIPELINE_TEMPLATE_GCS_PATH

.PHONY: help doctor sync test lint fmt fmt-check typecheck check \
        check-layers sync-dataform-config \
	tf-bootstrap tf-init tf-validate tf-fmt tf-fmt-fix tf-plan \
	setup-model-monitoring \
        setup-pipeline-schedule \
        apply-manifests \
        deploy-all deploy-all-direct run-all destroy-all seed-test seed-test-clean \
        train-smoke train-smoke-persist api-dev clean \
        docker-auth deploy-api deploy-kserve-models kube-creds \
		ops-deploy-monitor \
        ops-api-url ops-daily ops-livez ops-search ops-search-components ops-ranking ops-feedback \
        ops-accuracy-report local-accuracy-report \
        ops-skew-latest ops-search-volume ops-runs-recent \
	ops-skew-run ops-train-now ops-pipeline-run ops-promote-reranker ops-reload-api \
        ops-check-retrain ops-bq-scan-top ops-label-seed \
        ops-slo-status bqml-train-popularity enrich-properties \
        ops-kserve-monitoring

help: ## Show this help
	@echo "First-time setup:  see README.md §セットアップ (run 'make doctor' to verify tools)"
	@echo "Quick start:       make sync && make check && make train-smoke"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

doctor: ## Verify that prerequisite tools are installed
	uv run python -m scripts.setup.doctor

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
	uv run python -m scripts.setup.tf_bootstrap

tf-init: ## terraform init (with tfstate bucket preflight check)
	uv run python -m scripts.setup.tf_init

tf-validate: ## terraform validate (backend-less, works offline)
	terraform -chdir=$(TF_DIR) init -backend=false -upgrade=false >/dev/null
	terraform -chdir=$(TF_DIR) validate

tf-fmt: ## terraform fmt --check
	terraform -chdir=$(TF_DIR) fmt -check -diff

tf-fmt-fix: ## terraform fmt (writes)
	terraform -chdir=$(TF_DIR) fmt

tf-plan: ## terraform plan (requires GITHUB_REPO + ONCALL_EMAIL; saves tfplan)
	uv run python -m scripts.setup.tf_plan

setup-model-monitoring: ## Print resolved Vertex Model Monitoring setup payload
	uv run python -m scripts.setup.setup_model_monitoring

setup-pipeline-schedule: ## Print resolved Vertex Pipeline schedule setup payload
	uv run python -m scripts.setup.create_schedule

apply-manifests: ## Apply infra/manifests via kubectl apply -k
	kubectl apply -k $(ROOT)/infra/manifests

deploy-all: ## End-to-end provisioning + search-api rollout (tf-apply → kubectl apply -k → kserve_models → api_gke)
	uv run python -m scripts.setup.deploy_all

ops-deploy-monitor: ## Real-time monitor: runs deploy-all and reports live step/build stall status
	@mkdir -p "$(MONITOR_LOG_DIR)"
	@log_file="$(MONITOR_LOG_DIR)/$$(date -u +%Y%m%dT%H%M%SZ)-deploy-monitor.log"; \
	echo "monitor-log: $$log_file"; \
	bash -o pipefail -c 'uv run python -u -m scripts.deploy.monitor 2>&1 | tee "$$0"' "$$log_file"

deploy-all-direct: ## Compatibility alias of deploy-all (Phase4 naming)
	$(MAKE) deploy-all

run-all: ## End-to-end validation flow after deploy (layer check → seed → train pipeline submit → smoke APIs → daily ops)
	$(MAKE) ops-run-all-monitor

run-all-core: ## Core validation flow after deploy (no monitor wrapper)
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

ops-run-all-monitor: ## Real-time monitor for run-all-core
	@mkdir -p "$(MONITOR_LOG_DIR)"
	@log_file="$(MONITOR_LOG_DIR)/$$(date -u +%Y%m%dT%H%M%SZ)-run-all-monitor.log"; \
	echo "monitor-log: $$log_file"; \
	bash -o pipefail -c 'uv run python -u -m scripts.deploy.monitor --label run-all -- make run-all-core 2>&1 | tee "$$0"' "$$log_file"

verify-all: ## Alias of run-all-core for cross-phase teaching vocabulary
	$(MAKE) run-all-core

destroy-all: ## Tear down every Terraform-managed resource (no prompt — PDCA loop, pair with deploy-all)
	uv run python -m scripts.setup.destroy_all

destroy-phase7-learning: ## Coast-down placeholder: Dataflow Job / Feature Online Store / KServe explain pod
	@echo "Not implemented yet. See docs/04_運用.md for current manual coast-down guidance."
	@exit 1

seed-test: ## Insert 5 test properties for PDCA smoke
	uv run python -m scripts.setup.seed_minimal

seed-test-clean: ## Drop the test seed data (benign if absent)
	uv run python -m scripts.setup.seed_minimal_clean

# ----- App / Job smoke commands (local) -----

train-smoke: ## Dry-run the ranker training job locally (synthetic data, no GCS/BQ)
	uv run rank-train --dry-run

train-smoke-persist: ## Dry-run ranker trainer and copy the model to $(MODEL_PATH_OVERRIDE)
	uv run rank-train --dry-run --save-to "$(MODEL_PATH_OVERRIDE)"

api-dev: ## Start uvicorn locally (rerank-free /search requires ENABLE_SEARCH=1 + BQ creds)
	ENABLE_SEARCH=false uv run uvicorn app.main:app --reload

# ----- Local deploy path (bypasses CI; uses Cloud Build + kubectl) -----

docker-auth: ## (Optional) configure local docker for Artifact Registry
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet

kube-creds: ## Fetch kubeconfig for the Phase 6 GKE Autopilot cluster
	gcloud container clusters get-credentials $${GKE_CLUSTER_NAME:-hybrid-search} \
		--region=$(REGION) --project=$(PROJECT_ID)

deploy-api: ## Cloud Build + `kubectl set image` for search-api (Phase 6 replaces deploy-api-local)
	uv run python -m scripts.deploy.api_gke

deploy-kserve-models: ## Sync Model Registry artifacts into KServe InferenceService
	uv run python -m scripts.deploy.kserve_models

# ----- Housekeeping -----

clean: ## Remove caches (.venv, .terraform, pyc)
	rm -rf .venv $(TF_DIR)/.terraform
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache \) -prune -exec rm -rf {} +

# ----- GCP operations (see docs/04_運用.md §3) -----

ops-api-url: ## Print the search-api Gateway external URL
	@kubectl get gateway search-api-gateway --namespace=search -o jsonpath='{.status.addresses[0].value}' 2>/dev/null | sed -e 's|^|https://|' -e 's|$$||' || echo "search-api-gateway not yet provisioned"

ops-daily: ops-skew-latest ops-search-volume ops-runs-recent ## Run the 3 core daily checks

ops-skew-latest: ## Today's per-feature skew detection results (validation_results)
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/sql/skew_latest.sql

ops-search-volume: ## /search request volume over the last 24h
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/sql/search_volume.sql

ops-runs-recent: ## Last 5 LightGBM LambdaRank training runs
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/sql/runs_recent.sql

ops-skew-run: ## Ad-hoc execution of monitoring/validate_feature_skew.sql
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < monitoring/validate_feature_skew.sql

ops-bq-scan-top: ## Top 20 BQ scans in the last 7 days (cost audit)
	bq query --use_legacy_sql=false --project_id=$(PROJECT_ID) < scripts/sql/bq_scan_top.sql

ops-train-now: ## Submit train pipeline to Vertex AI
	uv run python -m pipeline.workflow.compile --target train --output-dir dist/pipelines --submit --project-id $(PROJECT_ID) --location $(VERTEX_LOCATION) --pipeline-root gs://$(PIPELINE_ROOT_BUCKET)/runs --service-account sa-pipeline@$(PROJECT_ID).iam.gserviceaccount.com

ops-pipeline-run: ## Submit a pipeline manually: TARGET=embed|train PARAM='key=value'
	uv run python -m pipeline.workflow.compile --target $${TARGET:-train} --output-dir dist/pipelines --submit --project-id $(PROJECT_ID) --location $(VERTEX_LOCATION) --pipeline-root gs://$(PIPELINE_ROOT_BUCKET)/runs --service-account sa-pipeline@$(PROJECT_ID).iam.gserviceaccount.com $${PARAM:+--parameter $$PARAM}

ops-promote-reranker: ## Promote a reranker to `production` alias. Usage: MODEL_ID=N or VERSION_ID=N [BST_RENAME=1] [APPLY=1].
	uv run python -m scripts.ops.promote reranker \
	  $${MODEL_ID:+--model-id=$${MODEL_ID}} \
	  $${VERSION_ID:+--version-id=$${VERSION_ID}} \
	  $${VERSION_ALIAS:+--version-alias=$${VERSION_ALIAS}} \
	  $${BST_RENAME:+--bst-rename} \
	  $${APPLY:+--apply}

ops-promote-encoder: ## Promote an encoder to `production` alias. Usage: MODEL_ID=N or VERSION_ID=N [APPLY=1].
	uv run python -m scripts.ops.promote encoder \
	  $${MODEL_ID:+--model-id=$${MODEL_ID}} \
	  $${VERSION_ID:+--version-id=$${VERSION_ID}} \
	  $${VERSION_ALIAS:+--version-alias=$${VERSION_ALIAS}} \
	  $${APPLY:+--apply}

ops-reload-api: ## Trigger a rolling restart of search-api Pods to re-read ConfigMap / model URIs
	kubectl rollout restart deployment/search-api --namespace=search

ops-livez: ## Hit /livez on the deployed search-api (IAM-gated)
	uv run python -m scripts.ops.livez

ops-search: ## POST /search smoke (override QUERY/TOP_K/MAX_RENT env vars)
	uv run python -m scripts.ops.search

ops-search-components: ## Strict gate: lexical/semantic/rerank contributions must all be non-zero
	uv run python -m scripts.ops.search_components

ops-ranking: ## POST /search and inspect lexical_rank / final_rank / score / me5_score
	uv run python -m scripts.ops.ranking

ops-feedback: ## /search → /feedback round-trip (publisher path smoke)
	uv run python -m scripts.ops.feedback

ops-label-seed: ## Seed feedback events (click/favorite/inquiry) against /search
	uv run python -m scripts.ops.label_seed

ops-check-retrain: ## POST /jobs/check-retrain with OIDC; pipe to jq
	uv run python -m scripts.ops.check_retrain

ops-accuracy-report: ## Simple ranking accuracy report on deployed Cloud Run (/search, TARGET=gcp)
	TARGET=gcp uv run python -m scripts.ops.accuracy_report

local-accuracy-report: ## Simple ranking accuracy report against local API (/search, TARGET=local)
	TARGET=local uv run python -m scripts.ops.accuracy_report

# ----- Phase 6 PMLE ops targets -----

ops-slo-status: ## Phase 6 T5: print current compliance + burn-rate (1h/3d) for availability + latency SLOs
	uv run python -m scripts.ops.slo_status

bqml-train-popularity: ## Phase 6 T1: train BQML property-popularity model (BOOSTED_TREE_REGRESSOR)
	uv run python -m scripts.bqml.train_popularity

enrich-properties: ## Phase 6 T8: run Gemini description enrichment (LIMIT=50 BATCH=10)
	uv run python -m scripts.enrichment.run_enrichment --limit=$${LIMIT:-50} --batch-size=$${BATCH:-10}

# ----- Vertex AI feature verification scripts (each ops target probes one Vertex
# AI surface in isolation. ops-vertex-all chains them; individual ones are useful
# when triaging which surface broke.)

ops-vertex-models-list: ## Vertex Model Registry: list versions/aliases for encoder/reranker
	uv run python -m scripts.ops.vertex_models_list

ops-vertex-pipeline-status: ## Vertex Pipelines: list latest runs + state (LIMIT=10)
	uv run python -m scripts.ops.vertex_pipeline_status

ops-vertex-rag: ## Vertex Gemini RAG via /rag (QUERY=...)
	uv run python -m scripts.ops.vertex_rag

ops-vertex-explain: ## Vertex Explainable AI via /search?explain=true (assert non-empty attributions)
	uv run python -m scripts.ops.vertex_explain

ops-vertex-monitoring: ## Vertex Model Monitoring: read recent BQ alert rows (LIMIT=10)
	uv run python -m scripts.ops.vertex_monitoring

ops-kserve-monitoring: ## Phase 7 self-managed drift alerts from model_monitoring_alerts (LIMIT=10)
	uv run python -m scripts.ops.vertex_monitoring

ops-vertex-feature-group: ## Vertex Feature Group: fetch online feature values for PROPERTY_ID=p001
	uv run python -m scripts.ops.vertex_feature_group

ops-vertex-all: ops-vertex-models-list ops-vertex-pipeline-status ops-vertex-explain ops-vertex-rag ops-vertex-monitoring ops-vertex-feature-group ## Run every Vertex AI smoke check in sequence
	@echo "==> all Vertex AI smoke checks completed"
