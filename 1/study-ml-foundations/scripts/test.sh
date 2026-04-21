#!/usr/bin/env bash
source "$(dirname "$0")/core.sh"

step "Running tests"
python3 -m pytest tests/ app/tests/ jobs/tests/ pipelines/tests/ -v "$@"
